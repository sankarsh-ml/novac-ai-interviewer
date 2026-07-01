from __future__ import annotations

from typing import Any

from app.infrastructure.storage.file_storage_service import read_file_from_mongo
from app.domain.rules.identity_rules import (
    GOVERNMENT_ID_SOURCE,
    RESUME_PHOTO_REQUIRED_MESSAGE,
    RESUME_PHOTO_SOURCE,
    normalize_face_source,
    normalize_identity_config,
    normalize_required,
)



def has_resume_photo(application: dict) -> bool:
    file_id = _resume_photo_file_id(application)

    if file_id:
        return read_file_from_mongo(file_id) is not None

    return False


def build_identity_config(application: dict, requested: dict | None = None) -> dict:
    stored = application.get("identityConfig") or application.get("identity_config")
    stored = stored if isinstance(stored, dict) else {}
    requested = requested if isinstance(requested, dict) else {}
    resume_photo_available = has_resume_photo(application)

    require_government_id = stored.get("requireGovernmentId")
    source = stored.get("faceVerificationSource")

    if "requireGovernmentId" in requested:
        require_government_id = requested.get("requireGovernmentId")
    elif "require_government_id" in requested:
        require_government_id = requested.get("require_government_id")

    if "faceVerificationSource" in requested:
        source = requested.get("faceVerificationSource")
    elif "face_verification_source" in requested:
        source = requested.get("face_verification_source")

    source = normalize_face_source(source)
    require_government_id = normalize_required(require_government_id, source)
    return normalize_identity_config(require_government_id, source, resume_photo_available)


def normalize_requested_identity_config(application: dict, payload: Any) -> dict:
    requested = {}

    if payload is not None:
        identity_config = getattr(payload, "identityConfig", None) or getattr(payload, "identity_config", None)
        if isinstance(identity_config, dict):
            requested.update(identity_config)
        elif hasattr(identity_config, "model_dump"):
            requested.update(identity_config.model_dump())

        if getattr(payload, "identityVerificationRequired", None) is not None:
            requested["requireGovernmentId"] = bool(getattr(payload, "identityVerificationRequired"))
        elif getattr(payload, "identity_verification_required", None) is not None:
            requested["requireGovernmentId"] = bool(getattr(payload, "identity_verification_required"))

    return build_identity_config(application, requested)


def requires_government_id(application: dict) -> bool:
    return build_identity_config(application).get("requireGovernmentId") is True


def _resume_photo_file_id(application: dict) -> str:
    resume = application.get("resume") if isinstance(application.get("resume"), dict) else {}
    parsed_resume = application.get("parsedResume") if isinstance(application.get("parsedResume"), dict) else {}
    candidates = [
        application.get("resumePhotoFileId"),
        application.get("resume_photo_file_id"),
        _gridfs_id(application.get("resume_face_image_path")),
        _gridfs_id(application.get("resume_photo_path")),
        resume.get("resumePhotoFileId"),
        resume.get("resume_photo_file_id"),
        _gridfs_id(resume.get("resume_face_image_path")),
        _gridfs_id(resume.get("resume_photo_path")),
        parsed_resume.get("photoFileId"),
        parsed_resume.get("photo_file_id"),
    ]

    for candidate in candidates:
        value = str(candidate or "").strip()
        if value:
            return value

    return ""


def _gridfs_id(path_value: Any) -> str:
    path_text = str(path_value or "").strip()
    return path_text.replace("gridfs://", "", 1) if path_text.startswith("gridfs://") else ""

