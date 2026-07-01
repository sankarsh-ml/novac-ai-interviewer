from __future__ import annotations

from app.application.services.face_verification_service import (
    DEFAULT_FACE_VERIFY_THRESHOLD,
    analyze_face_image_bytes,
    cosine_similarity,
    get_dependency_status,
    get_face_app,
    verify_faces,
)


def verify(reference_image_path: str, live_frame_path: str, threshold: float = DEFAULT_FACE_VERIFY_THRESHOLD) -> dict:
    return verify_faces(reference_image_path, live_frame_path, threshold=threshold)
