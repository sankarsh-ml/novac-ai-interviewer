import os

# These must be set before PaddleOCR imports Paddle.
os.environ["FLAGS_use_onednn"] = "0"
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"

import argparse
import json
import logging
from pathlib import Path

import cv2
from huggingface_hub import hf_hub_download
from ultralytics import YOLO


REPO_ID = "logasanjeev/indian-id-validator"
SCRIPT_DIR = Path(__file__).resolve().parent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("ultralytics").setLevel(logging.WARNING)

CONFIG = None
OCR = None
MODEL_CACHE = {}


def load_config(config_path=None):
    config_path = Path(config_path) if config_path else SCRIPT_DIR / "config.json"

    if not config_path.exists():
        config_path = hf_hub_download(
            repo_id=REPO_ID,
            filename="config.json",
        )

    with open(config_path, "r", encoding="utf-8") as file:
        return json.load(file)


def get_config():
    global CONFIG

    if CONFIG is None:
        CONFIG = load_config()

    return CONFIG


def get_ocr():
    """
    Uses old stable PaddleOCR style.
    Best with:
      paddlepaddle==2.6.2
      paddleocr==2.7.3
    """
    global OCR

    if OCR is None:
        from paddleocr import PaddleOCR

        try:
            OCR = PaddleOCR(
                use_angle_cls=True,
                lang="en",
                show_log=False,
                use_gpu=False,
            )
        except TypeError:
            # Fallback for newer PaddleOCR versions, though 2.7.3 is recommended.
            OCR = PaddleOCR(
                use_angle_cls=True,
                lang="en",
                use_gpu=False,
            )

    return OCR


def load_model(model_key):
    config = get_config()

    if model_key in MODEL_CACHE:
        return MODEL_CACHE[model_key]

    if model_key not in config["models"]:
        raise ValueError(f"Invalid model name: {model_key}")

    model_path = Path(config["models"][model_key]["path"])

    if not model_path.is_absolute():
        model_path = SCRIPT_DIR / model_path

    if not model_path.exists():
        model_path = hf_hub_download(
            repo_id=REPO_ID,
            filename=config["models"][model_key]["path"],
        )

    model = YOLO(str(model_path))
    MODEL_CACHE[model_key] = model

    return model


def read_text_from_crop(crop):
    """
    OCR only the detected field crop.
    No upscaling, denoising, black canvas, plotting, or extra preprocessing.
    """
    if crop is None or crop.size == 0:
        return "No text detected"

    ocr = get_ocr()

    try:
        ocr_result = ocr.ocr(crop, cls=True)
    except TypeError:
        ocr_result = ocr.ocr(crop)

    if not ocr_result:
        return "No text detected"

    extracted_text = []

    for line in ocr_result:
        if line is None:
            continue

        for word_info in line:
            if word_info is None:
                continue

            if len(word_info) >= 2 and word_info[1]:
                text = word_info[1][0]
                if text:
                    extracted_text.append(str(text).strip())

    final_text = " ".join(extracted_text).strip()
    return final_text if final_text else "No text detected"


def classify_document(image):
    classifier = load_model("Id_Classifier")
    results = classifier(image, verbose=False)

    if not results or results[0].probs is None:
        return {
            "doc_type": "unknown",
            "document_type": "unknown",
            "confidence": 0.0,
        }

    doc_type = results[0].names[results[0].probs.top1]
    confidence = float(results[0].probs.top1conf.item())

    logger.info(f"Detected document type: {doc_type}, confidence: {confidence:.2f}")

    return {
        "doc_type": doc_type,
        "document_type": doc_type,
        "confidence": confidence,
    }


def _clip_box(x_min, y_min, x_max, y_max, width, height, padding=0):
    x_min = max(0, int(x_min) - padding)
    y_min = max(0, int(y_min) - padding)
    x_max = min(width, int(x_max) + padding)
    y_max = min(height, int(y_max) + padding)

    return x_min, y_min, x_max, y_max


def process_id(
    image_path,
    model_name=None,
    save_json=True,
    output_json="detected_text.json",
    verbose=False,
    classify_only=False,
):
    """
    Indian ID validation pipeline:

    1. If model_name is None:
       Use Id_Classifier to classify the document.
    2. Use mapped YOLO detector for that ID type.
    3. For every detected field box:
       crop exact field and OCR only that crop.
    4. Return JSON-like dict.

    This intentionally avoids:
    - image upscaling
    - denoising
    - sharpening
    - CLAHE
    - black canvas
    - matplotlib visualization
    """

    config = get_config()

    image_path = str(image_path)
    image = cv2.imread(image_path)

    if image is None:
        raise ValueError(f"Failed to load image: {image_path}")

    if model_name is None:
        classification = classify_document(image)
        doc_type = classification["doc_type"]
        confidence = classification["confidence"]

        if classify_only:
            return {
                "doc_type": doc_type,
                "document_type": doc_type,
                "confidence": confidence,
            }

        model_name = config["doc_type_to_model"].get(doc_type)

        if model_name is None:
            logger.warning(f"No detection model mapped for document type: {doc_type}")
            empty_result = {
                "doc_type": doc_type,
                "document_type": doc_type,
                "confidence": confidence,
                "fields": {},
            }

            if save_json:
                with open(output_json, "w", encoding="utf-8") as file:
                    json.dump(empty_result, file, indent=4, ensure_ascii=False)

            return empty_result

    if model_name not in config["models"]:
        raise ValueError(f"Invalid model name: {model_name}")

    model = load_model(model_name)
    class_names = config["models"][model_name]["classes"]

    results = model(image_path, verbose=False)

    if not results:
        return {}

    height, width = image.shape[:2]
    best_boxes = {}

    for result in results:
        if result.boxes is None:
            continue

        for box in result.boxes:
            cls = int(box.cls[0].item())
            conf = float(box.conf[0].item())

            if cls >= len(class_names):
                continue

            class_name = class_names[cls]
            xyxy = box.xyxy[0].tolist()

            if class_name not in best_boxes or conf > best_boxes[class_name]["confidence"]:
                best_boxes[class_name] = {
                    "confidence": conf,
                    "xyxy": xyxy,
                }

    detected_text = {}

    for class_name, box_data in best_boxes.items():
        x_min, y_min, x_max, y_max = box_data["xyxy"]

        x_min, y_min, x_max, y_max = _clip_box(
            x_min,
            y_min,
            x_max,
            y_max,
            width,
            height,
            padding=0,
        )

        crop = image[y_min:y_max, x_min:x_max]

        text = read_text_from_crop(crop)

        detected_text[class_name] = text

        logger.info(
            f"{class_name}: {text} "
            f"(confidence={box_data['confidence']:.2f}, box={[x_min, y_min, x_max, y_max]})"
        )

    if save_json:
        with open(output_json, "w", encoding="utf-8") as file:
            json.dump(detected_text, file, indent=4, ensure_ascii=False)

    return detected_text


def aadhaar(image_path, save_json=True, output_json="detected_text.json", verbose=False):
    return process_id(
        image_path=image_path,
        model_name="Aadhaar",
        save_json=save_json,
        output_json=output_json,
        verbose=verbose,
    )


def pan_card(image_path, save_json=True, output_json="detected_text.json", verbose=False):
    return process_id(
        image_path=image_path,
        model_name="Pan_Card",
        save_json=save_json,
        output_json=output_json,
        verbose=verbose,
    )


def passport(image_path, save_json=True, output_json="detected_text.json", verbose=False):
    return process_id(
        image_path=image_path,
        model_name="Passport",
        save_json=save_json,
        output_json=output_json,
        verbose=verbose,
    )


def voter_id(image_path, save_json=True, output_json="detected_text.json", verbose=False):
    return process_id(
        image_path=image_path,
        model_name="Voter_Id",
        save_json=save_json,
        output_json=output_json,
        verbose=verbose,
    )


def driving_license(image_path, save_json=True, output_json="detected_text.json", verbose=False):
    return process_id(
        image_path=image_path,
        model_name="Driving_License",
        save_json=save_json,
        output_json=output_json,
        verbose=verbose,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Indian ID Validator: classify and extract fields from Indian ID images."
    )

    parser.add_argument("image_path", help="Path to input ID image")
    parser.add_argument(
        "--model",
        default=None,
        choices=["Aadhaar", "Pan_Card", "Passport", "Voter_Id", "Driving_License"],
        help="Specific model to use. If omitted, classifier is used first.",
    )
    parser.add_argument(
        "--no-save-json",
        action="store_false",
        dest="save_json",
        help="Disable saving JSON output.",
    )
    parser.add_argument(
        "--output-json",
        default="detected_text.json",
        help="Path to save JSON output.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Accepted for compatibility. No plots are shown in this simplified version.",
    )
    parser.add_argument(
        "--classify-only",
        action="store_true",
        dest="classify_only",
        help="Only classify document type.",
    )

    args = parser.parse_args()

    result = process_id(
        image_path=args.image_path,
        model_name=args.model,
        save_json=args.save_json,
        output_json=args.output_json,
        verbose=args.verbose,
        classify_only=args.classify_only,
    )

    print(json.dumps(result, indent=4, ensure_ascii=False))
