import importlib
import os
from pathlib import Path


def _get_default_threshold():
    try:
        return float(os.getenv("FACE_VERIFY_THRESHOLD", "0.38"))
    except (TypeError, ValueError):
        return 0.38


DEFAULT_FACE_VERIFY_THRESHOLD = _get_default_threshold()

FACE_APP = None
FACE_IMPORT_ERROR = None

try:
    import cv2
    import numpy as np
    import onnxruntime  # noqa: F401
    from insightface.app import FaceAnalysis
    from numpy.linalg import norm
except Exception as error:
    FACE_IMPORT_ERROR = error


def get_face_app():
    global FACE_APP

    if FACE_APP is not None:
        return FACE_APP

    if FACE_IMPORT_ERROR is not None:
        raise RuntimeError(
            "Face verification import error: "
            f"{type(FACE_IMPORT_ERROR).__name__}: {FACE_IMPORT_ERROR}"
        )

    try:
        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=(640, 640))
    except Exception as error:
        raise RuntimeError(
            "FaceAnalysis initialization failed: "
            f"{type(error).__name__}: {error}"
        ) from error

    FACE_APP = app
    return FACE_APP


def get_largest_face_embedding(image_path: str):
    image_file = Path(str(image_path)).expanduser()

    if not image_file.exists():
        return {
            "success": False,
            "embedding": None,
            "message": f"Image path does not exist: {image_file}",
        }

    app = get_face_app()
    image = cv2.imread(str(image_file))

    if image is None:
        return {
            "success": False,
            "embedding": None,
            "message": f"Image could not be loaded: {image_file}",
        }

    faces = app.get(image)

    if not faces:
        return {
            "success": False,
            "embedding": None,
            "message": f"No face detected in image: {image_file}",
        }

    largest_face = max(faces, key=_face_bbox_area)

    return {
        "success": True,
        "embedding": largest_face.embedding,
        "message": "Face detected",
    }


def cosine_similarity(a, b):
    vector_a = np.asarray(a, dtype="float32")
    vector_b = np.asarray(b, dtype="float32")

    norm_a = norm(vector_a)
    norm_b = norm(vector_b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(vector_a, vector_b) / (norm_a * norm_b))


def verify_faces(reference_image_path: str, live_frame_path: str, threshold: float = DEFAULT_FACE_VERIFY_THRESHOLD):
    try:
        reference_result = get_largest_face_embedding(reference_image_path)
        if not reference_result.get("success"):
            return _failure(reference_result.get("message", "No face detected in reference image"), threshold)

        live_result = get_largest_face_embedding(live_frame_path)
        if not live_result.get("success"):
            return _failure(_live_frame_message(live_result.get("message")), threshold)

        score = cosine_similarity(reference_result["embedding"], live_result["embedding"])
        rounded_score = round(float(score), 4)
        match = rounded_score >= threshold

        return {
            "success": True,
            "match": match,
            "score": rounded_score,
            "threshold": threshold,
            "message": "Face match passed" if match else "Face match failed",
        }

    except Exception as error:
        return _failure(_exception_message(error), threshold)


def _face_bbox_area(face):
    x1, y1, x2, y2 = face.bbox
    return max(0.0, float(x2) - float(x1)) * max(0.0, float(y2) - float(y1))


def _failure(message: str, threshold: float):
    return {
        "success": False,
        "match": False,
        "score": 0.0,
        "threshold": threshold,
        "message": message,
    }


def _exception_message(error: Exception):
    message = str(error).strip()

    if message:
        return message

    return type(error).__name__


def _live_frame_message(message):
    if not message:
        return "No face detected in live frame"

    if message.startswith("No face detected in image:"):
        return "No face detected in live frame"

    return message


def get_dependency_status():
    dependencies = {}
    errors = {}

    for module_name in ("insightface", "onnxruntime", "cv2", "numpy"):
        try:
            importlib.import_module(module_name)
            dependencies[module_name] = "ok"
        except Exception as error:
            dependencies[module_name] = "failed"
            errors[module_name] = f"{type(error).__name__}: {error}"

    return dependencies, errors
