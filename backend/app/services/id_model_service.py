import json
import os
import json
from pathlib import Path
import re
import shutil
import subprocess
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[3]
APP_DIR = Path(__file__).resolve().parents[1]

AADHAAR_PHOTO_STORAGE_DIR = APP_DIR / "storage" / "aadhaar_photos"
AADHAAR_PHOTO_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

VALIDATOR_TIMEOUT_SECONDS = 90
SUPPORTED_INDIAN_ID_MODELS = {
    "aadhaar": "Aadhaar",
    "aadhar": "Aadhaar",
    "aadhar_front": "Aadhaar",
    "aadhar_back": "Aadhaar",
    "aadhaar_front": "Aadhaar",
    "aadhaar_back": "Aadhaar",
    "pan": "Pan_Card",
    "pan_card": "Pan_Card",
    "pan_card_front": "Pan_Card",
    "passport": "Passport",
    "voter": "Voter_Id",
    "voter_id": "Voter_Id",
    "driving_license": "Driving_License",
    "driving_license_front": "Driving_License",
    "driving_license_back": "Driving_License",
}


def _default_indian_id_python() -> Path:
    return PROJECT_ROOT / "id_venv" / "Scripts" / "python.exe"


def _default_indian_id_inference() -> Path:
    return PROJECT_ROOT / "indian-id-validator" / "inference.py"


def _resolve_path_from_env(env_name: str, default_path: Path) -> Path:
    configured = os.getenv(env_name)

    if not configured:
        return default_path

    path = Path(configured)
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def _extract_last_json_object(stdout: str) -> dict:
    decoder = json.JSONDecoder()
    text = (stdout or "").strip()

    for index in range(len(text) - 1, -1, -1):
        if text[index] != "{":
            continue

        candidate = text[index:]

        try:
            parsed, end_index = decoder.raw_decode(candidate)
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, dict) and not candidate[end_index:].strip():
            return parsed

    raise ValueError("No JSON object found in Indian ID validator stdout.")


def run_indian_id_validator(
    image_path: str,
    model: str = "Aadhaar",
    classify_only: bool = False,
) -> dict:
    indian_id_python = _resolve_path_from_env("INDIAN_ID_PYTHON", _default_indian_id_python())
    indian_id_inference = _resolve_path_from_env(
        "INDIAN_ID_INFERENCE",
        _default_indian_id_inference(),
    )

    if not indian_id_python.exists():
        return {
            "success": False,
            "error": f"Indian ID Python not found: {indian_id_python}",
            "stdout": "",
            "stderr": "",
        }

    if not indian_id_inference.exists():
        return {
            "success": False,
            "error": f"Indian ID inference.py not found: {indian_id_inference}",
            "stdout": "",
            "stderr": "",
        }

    command = [
        str(indian_id_python),
        str(indian_id_inference),
        str(image_path),
    ]

    if classify_only:
        command.extend(["--classify-only", "--no-save-json"])
    else:
        command.extend(["--model", model, "--no-save-json"])

    env = os.environ.copy()
    env["FLAGS_use_onednn"] = "0"
    env["FLAGS_use_mkldnn"] = "0"
    env["FLAGS_enable_pir_api"] = "0"

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=VALIDATOR_TIMEOUT_SECONDS,
            cwd=str(indian_id_inference.parent),
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "success": False,
            "error": f"Indian ID validator timed out after {VALIDATOR_TIMEOUT_SECONDS} seconds.",
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "command": command,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": f"Indian ID validator subprocess failed to start: {exc}",
            "stdout": "",
            "stderr": "",
            "command": command,
        }

    if completed.returncode != 0:
        return {
            "success": False,
            "error": f"Indian ID validator exited with code {completed.returncode}.",
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "command": command,
        }

    try:
        return _extract_last_json_object(completed.stdout)
    except Exception as exc:
        return {
            "success": False,
            "error": f"Indian ID validator returned unparsable output: {exc}",
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "command": command,
        }


def _ensure_image_file(file_path: str) -> str:
    path = Path(file_path)

    if path.suffix.lower() != ".pdf":
        return str(path)

    output_path = path.with_suffix(".page1.jpg")

    if output_path.exists():
        return str(output_path)

    import fitz

    document = fitz.open(str(path))

    try:
        page = document[0]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        pixmap.save(str(output_path))
        return str(output_path)
    finally:
        document.close()


def _flatten_mapping(mapping, prefix=""):
    flattened = {}

    if not isinstance(mapping, dict):
        return flattened

    for key, value in mapping.items():
        full_key = f"{prefix}_{key}".strip("_").lower()

        if isinstance(value, dict):
            flattened.update(_flatten_mapping(value, full_key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, dict):
                    flattened.update(_flatten_mapping(item, f"{full_key}_{index}"))
                else:
                    flattened[f"{full_key}_{index}"] = item
        else:
            flattened[full_key] = value

    return flattened


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", key.lower()).strip("_")


def _first_value(mapping, candidate_keys):
    normalized_candidates = [_normalize_key(candidate) for candidate in candidate_keys]

    for key, value in mapping.items():
        normalized_key = _normalize_key(key)

        if normalized_key in normalized_candidates:
            text = str(value).strip()

            if text and text.lower() not in ["none", "null", "no text detected"]:
                return text

    for key, value in mapping.items():
        normalized_key = _normalize_key(key)

        if any(candidate in normalized_key for candidate in normalized_candidates):
            text = str(value).strip()

            if text and text.lower() not in ["none", "null", "no text detected"]:
                return text

    return ""


def _extract_document_type(raw_output):
    if not isinstance(raw_output, dict):
        return "unknown"

    flattened = _flatten_mapping(raw_output)

    for key in [
        "document_type",
        "doc_type",
        "id_type",
        "prediction",
        "predicted_class",
        "class",
        "label",
        "type",
    ]:
        value = _first_value(flattened, [key])

        if value:
            return value.strip().lower()

    return "unknown"


def _normalize_document_type(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")

    if "aadhar" in text or "aadhaar" in text:
        return "aadhaar"

    if "pan" in text:
        return "pan"

    if "passport" in text:
        return "passport"

    if "voter" in text:
        return "voter_id"

    if "driving" in text or text in {"dl", "license", "licence"}:
        return "driving_license"

    return text or "unknown"


def _model_for_document_type(document_type: str) -> str | None:
    return SUPPORTED_INDIAN_ID_MODELS.get(_normalize_document_type(document_type))


def _extract_confidence(raw_output):
    if not isinstance(raw_output, dict):
        return 0.0

    flattened = _flatten_mapping(raw_output)

    for key, value in flattened.items():
        normalized_key = key.lower()

        if any(word in normalized_key for word in ["confidence", "score", "probability", "prob"]):
            try:
                return round(float(value), 4)
            except Exception:
                pass

    return 0.0


def _find_aadhaar_number(text):
    text = text or ""

    full_match = re.search(r"\b\d{4}\s?\d{4}\s?\d{4}\b", text)

    if full_match:
        return full_match.group(0)

    masked_match = re.search(r"[Xx]{4,}\s*\d{4}", text)

    if masked_match:
        return masked_match.group(0)

    return ""


def _mask_aadhaar_number(number: str) -> str:
    if not number:
        return ""

    digits = re.sub(r"\D", "", number)

    if len(digits) >= 4:
        return f"XXXX XXXX {digits[-4:]}"

    masked_match = re.search(r"[Xx]{4,}\s*(\d{4})", number)

    if masked_match:
        return f"XXXX XXXX {masked_match.group(1)}"

    return ""


def _mask_aadhaar_text(value: str) -> str:
    def replace_full(match):
        return _mask_aadhaar_number(match.group(0))

    masked = re.sub(r"\b\d{4}\s?\d{4}\s?\d{4}\b", replace_full, value)
    masked = re.sub(
        r"\b(?:[Xx]{4}\s*){2}\d{4}\b",
        lambda match: _mask_aadhaar_number(match.group(0)),
        masked,
    )
    masked = re.sub(
        r"\b[Xx]{8}\s?\d{4}\b",
        lambda match: _mask_aadhaar_number(match.group(0)),
        masked,
    )
    return masked


def _sanitize_raw_output(value):
    if isinstance(value, dict):
        return {key: _sanitize_raw_output(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_sanitize_raw_output(item) for item in value]

    if isinstance(value, str):
        return _mask_aadhaar_text(value)

    return value


def _extract_fields_from_raw_output(raw_output):
    flattened = _flatten_mapping(raw_output if isinstance(raw_output, dict) else {})
    all_text = " ".join(str(value) for value in flattened.values())

    name = _first_value(
        flattened,
        [
            "name",
            "Name",
            "full_name",
            "aadhaar_name",
            "aadhar_name",
            "applicant_name",
            "holder_name",
        ],
    )

    dob = _first_value(
        flattened,
        [
            "DOB",
            "dob",
            "date_of_birth",
            "birth",
            "birth_date",
            "yob",
            "year_of_birth",
        ],
    )

    gender = _first_value(
        flattened,
        [
            "gender",
            "Gender",
            "sex",
        ],
    )

    aadhaar_number = _first_value(
        flattened,
        [
            "Aadhaar_Number",
            "aadhaar_number",
            "aadhar_number",
            "uid",
            "id_number",
            "pan",
            "pan_number",
            "passport_number",
            "voter_id",
            "voter_number",
            "dl_no",
            "dl_number",
            "license_number",
            "licence_number",
        ],
    )

    if not _mask_aadhaar_number(aadhaar_number):
        aadhaar_number = _find_aadhaar_number(all_text)

    return {
        "name": name,
        "dob": dob,
        "gender": gender,
        "aadhaar_number": aadhaar_number,
        "masked_aadhaar_number": _mask_aadhaar_number(aadhaar_number),
        "flattened": flattened,
    }


def classify_indian_government_id(file_path: str) -> dict:
    try:
        image_path = _ensure_image_file(file_path)
    except Exception as exc:
        return {
            "success": False,
            "documentType": "unknown",
            "document_type": "unknown",
            "isValidIndianGovId": False,
            "confidence": 0.0,
            "message": f"Indian Government ID file could not be prepared for validation: {exc}",
            "raw_output": {},
        }

    raw_output = run_indian_id_validator(image_path, classify_only=True)

    if raw_output.get("success") is False:
        return {
            "success": False,
            "documentType": "unknown",
            "document_type": "unknown",
            "isValidIndianGovId": False,
            "confidence": 0.0,
            "message": raw_output.get("error") or "Indian ID validator failed.",
            "raw_output": _sanitize_raw_output(raw_output),
        }

    raw_document_type = _extract_document_type(raw_output)
    document_type = _normalize_document_type(raw_document_type)
    valid = _model_for_document_type(document_type) is not None

    return {
        "success": True,
        "documentType": document_type if valid else "unknown",
        "document_type": document_type if valid else "unknown",
        "rawDocumentType": raw_document_type,
        "raw_document_type": raw_document_type,
        "isValidIndianGovId": valid,
        "is_valid_indian_gov_id": valid,
        "confidence": _extract_confidence(raw_output),
        "message": "Indian Government ID detected" if valid else "Unsupported or unknown Indian ID document",
        "raw_output": _sanitize_raw_output(raw_output),
    }


def extract_indian_id_fields(file_path: str, document_type: str) -> dict:
    try:
        image_path = _ensure_image_file(file_path)
    except Exception as exc:
        return {
            "success": False,
            "message": f"Indian Government ID file could not be prepared for field extraction: {exc}",
            "name": "",
            "dob": "",
            "idNumber": "",
            "id_number": "",
            "raw_output": {},
        }

    model = _model_for_document_type(document_type)

    if not model:
        return {
            "success": False,
            "message": "Unsupported or unknown Indian ID document.",
            "name": "",
            "dob": "",
            "idNumber": "",
            "id_number": "",
            "raw_output": {},
        }

    raw_output = run_indian_id_validator(image_path, model=model, classify_only=False)

    if raw_output.get("success") is False:
        return {
            "success": False,
            "message": raw_output.get("error") or "Indian ID validator extraction failed.",
            "name": "",
            "dob": "",
            "idNumber": "",
            "id_number": "",
            "raw_output": _sanitize_raw_output(raw_output),
        }

    fields = _extract_fields_from_raw_output(raw_output)
    id_number = fields["masked_aadhaar_number"] or fields["aadhaar_number"]

    return {
        "success": bool(fields["name"] or id_number),
        "message": "Indian Government ID fields extracted" if (fields["name"] or id_number) else "Indian Government ID fields could not be extracted",
        "name": fields["name"],
        "dob": fields["dob"],
        "gender": fields["gender"],
        "idNumber": id_number,
        "id_number": id_number,
        "aadhaar_number": fields["masked_aadhaar_number"] if _normalize_document_type(document_type) == "aadhaar" else "",
        "masked_aadhaar_number": fields["masked_aadhaar_number"] if _normalize_document_type(document_type) == "aadhaar" else "",
        "raw_output": _sanitize_raw_output(raw_output),
        "raw_keys": list(fields["flattened"].keys()),
    }


def _has_aadhaar_fields(raw_output: dict) -> bool:
    fields = _extract_fields_from_raw_output(raw_output)
    raw_text = json.dumps(raw_output, ensure_ascii=False).lower()

    return bool(
        fields["masked_aadhaar_number"]
        or fields["name"]
        or "aadhaar" in raw_text
        or "aadhar" in raw_text
    )


def is_aadhaar_card(file_path: str) -> dict:
    try:
        image_path = _ensure_image_file(file_path)
    except Exception as exc:
        return {
            "success": False,
            "is_aadhaar": False,
            "confidence": 0.0,
            "document_type": "unknown",
            "message": f"Aadhaar file could not be prepared for validation: {exc}",
            "raw_output": {},
        }

    raw_output = run_indian_id_validator(image_path, classify_only=True)

    if raw_output.get("success") is False:
        fallback_output = run_indian_id_validator(image_path, model="Aadhaar", classify_only=False)

        if fallback_output.get("success") is False:
            return {
                "success": False,
                "is_aadhaar": False,
                "confidence": 0.0,
                "document_type": "unknown",
                "message": raw_output.get("error") or fallback_output.get("error") or "Indian ID validator failed.",
                "raw_output": _sanitize_raw_output(fallback_output),
            }

        detected = _has_aadhaar_fields(fallback_output)

        return {
            "success": True,
            "is_aadhaar": detected,
            "confidence": _extract_confidence(fallback_output),
            "document_type": "aadhaar" if detected else "unknown",
            "message": "Aadhaar card detected" if detected else "No valid Aadhaar detected",
            "raw_output": _sanitize_raw_output(fallback_output),
        }

    document_type = _extract_document_type(raw_output)
    confidence = _extract_confidence(raw_output)
    raw_text = json.dumps(raw_output, ensure_ascii=False).lower()

    detected = (
        "aadhaar" in document_type
        or "aadhar" in document_type
        or "aadhaar" in raw_text
        or "aadhar" in raw_text
    )

    return {
        "success": True,
        "is_aadhaar": detected,
        "confidence": confidence,
        "document_type": "aadhaar" if detected else document_type,
        "message": "Aadhaar card detected" if detected else "No valid Aadhaar detected",
        "raw_output": _sanitize_raw_output(raw_output),
    }


def extract_aadhaar_fields(file_path: str) -> dict:
    try:
        image_path = _ensure_image_file(file_path)
    except Exception as exc:
        return {
            "success": False,
            "message": f"Aadhaar file could not be prepared for field extraction: {exc}",
            "name": "",
            "aadhaar_number": "",
            "masked_aadhaar_number": "",
            "dob": "",
            "gender": "",
            "raw_output": {},
        }

    raw_output = run_indian_id_validator(image_path, model="Aadhaar", classify_only=False)

    if raw_output.get("success") is False:
        return {
            "success": False,
            "message": raw_output.get("error") or "Indian ID validator Aadhaar extraction failed.",
            "name": "",
            "aadhaar_number": "",
            "masked_aadhaar_number": "",
            "dob": "",
            "gender": "",
            "raw_output": _sanitize_raw_output(raw_output),
        }

    fields = _extract_fields_from_raw_output(raw_output)
    masked_aadhaar_number = fields["masked_aadhaar_number"]

    return {
        "success": bool(fields["name"] or masked_aadhaar_number),
        "message": "Aadhaar fields extracted" if (fields["name"] or masked_aadhaar_number) else "Aadhaar fields could not be extracted",
        "name": fields["name"],
        "aadhaar_number": masked_aadhaar_number,
        "masked_aadhaar_number": masked_aadhaar_number,
        "dob": fields["dob"],
        "gender": fields["gender"],
        "raw_output": _sanitize_raw_output(raw_output),
        "raw_keys": list(fields["flattened"].keys()),
    }


def extract_aadhaar_photo(file_path: str, application_id: str | None = None) -> dict:
    try:
        image_path = Path(_ensure_image_file(file_path))
    except Exception:
        image_path = Path(file_path)

    if application_id:
        output_dir = APP_DIR / "storage" / "candidates" / application_id / "aadhaar_faces"
    else:
        output_dir = AADHAAR_PHOTO_STORAGE_DIR

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        try:
            import cv2
        except Exception as exc:
            fallback_path = output_dir / f"{uuid.uuid4()}_{image_path.name}"
            shutil.copyfile(image_path, fallback_path)

            return {
                "available": True,
                "path": str(fallback_path),
                "photo_available": True,
                "photo_path": str(fallback_path),
                "message": f"OpenCV unavailable in backend venv; stored uploaded Aadhaar image instead: {exc}",
            }

        image = cv2.imread(str(image_path))

        if image is None:
            return {
                "available": False,
                "path": "",
                "photo_available": False,
                "photo_path": None,
                "message": "Aadhaar image could not be read",
            }

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        classifier_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        detector = cv2.CascadeClassifier(classifier_path)

        faces = detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(35, 35),
        )

        if len(faces) == 0:
            fallback_path = output_dir / f"{uuid.uuid4()}_{image_path.name}"
            shutil.copyfile(image_path, fallback_path)

            return {
                "available": True,
                "path": str(fallback_path),
                "photo_available": True,
                "photo_path": str(fallback_path),
                "message": "Aadhaar face crop unavailable; stored uploaded Aadhaar image for development",
            }

        x, y, width, height = max(faces, key=lambda face: face[2] * face[3])
        padding = int(max(width, height) * 0.25)

        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(image.shape[1], x + width + padding)
        y2 = min(image.shape[0], y + height + padding)

        crop = image[y1:y2, x1:x2]
        output_path = output_dir / f"{uuid.uuid4()}_aadhaar_face.jpg"
        cv2.imwrite(str(output_path), crop)

        return {
            "available": True,
            "path": str(output_path),
            "photo_available": True,
            "photo_path": str(output_path),
            "message": "Aadhaar photo extracted",
        }

    except Exception as exc:
        return {
            "available": False,
            "path": "",
            "photo_available": False,
            "photo_path": None,
            "message": f"Aadhaar photo extraction failed: {exc}",
        }
