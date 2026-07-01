from __future__ import annotations

GOVERNMENT_ID_SOURCE = "government_id"
RESUME_PHOTO_SOURCE = "resume_photo"
RESUME_PHOTO_REQUIRED_MESSAGE = "Resume photo is not available. Indian Government ID verification is required."


def normalize_identity_config(
    require_government_id,
    face_verification_source,
    resume_photo_available: bool,
) -> dict:
    source = normalize_face_source(face_verification_source)
    required = normalize_required(require_government_id, source)

    if not resume_photo_available:
        required = True
        source = GOVERNMENT_ID_SOURCE
    elif required:
        source = GOVERNMENT_ID_SOURCE
    elif source != RESUME_PHOTO_SOURCE:
        source = RESUME_PHOTO_SOURCE

    return {
        "requireGovernmentId": bool(required),
        "faceVerificationSource": source,
        "resumePhotoAvailable": bool(resume_photo_available),
    }


def validate_skip_allowed(skip_requested: bool, resume_photo_available: bool) -> None:
    if skip_requested and not resume_photo_available:
        from app.domain.exceptions import ValidationError

        raise ValidationError(RESUME_PHOTO_REQUIRED_MESSAGE)


def normalize_face_source(source) -> str:
    normalized = str(source or GOVERNMENT_ID_SOURCE).strip().lower()
    if normalized in {"resume", "resume_face", "resume_photo"}:
        return RESUME_PHOTO_SOURCE
    return GOVERNMENT_ID_SOURCE


def normalize_required(value, source: str) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return source != RESUME_PHOTO_SOURCE

    return str(value).strip().lower() not in {"false", "0", "no", "skip", "resume_photo"}


def can_start_interview(require_government_id: bool, government_id_verified: bool, face_verified: bool) -> bool:
    return face_verified and (government_id_verified or not require_government_id)
