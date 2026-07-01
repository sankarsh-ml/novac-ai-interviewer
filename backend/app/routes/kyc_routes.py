import os
import shutil
import traceback
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.application.services.application_store_service import get_resume_application, update_application
from app.application.services.identity_config_service import (
    GOVERNMENT_ID_SOURCE,
    RESUME_PHOTO_SOURCE,
    build_identity_config,
    requires_government_id,
)
from app.application.services.identity_service import save_file_to_mongo, save_path_to_mongo, verify_indian_id_for_application
from app.core.config import get_path


router = APIRouter()

GOVERNMENT_ID_UPLOAD_DIR = get_path("id_temp_dir")
GOVERNMENT_ID_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CANDIDATE_STORAGE_DIR = get_path("candidate_temp_dir")

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}

try:
    from bson import ObjectId
except Exception:
    ObjectId = None


class MarkVerifiedRequest(BaseModel):
    reference_source: str = ""
    face_score: float | None = None
    attempts: int = 1
    matches: int = 1


def make_json_safe(data):
    custom_encoder = {}

    if ObjectId is not None:
        custom_encoder[ObjectId] = str

    return jsonable_encoder(data, custom_encoder=custom_encoder)


def _kyc_json_response(payload: dict, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=make_json_safe(payload))


@router.get("/candidate/{application_id}")
def get_candidate_verification_data(application_id: str):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return {
        "success": True,
        "data": _candidate_verification_payload(application),
    }


@router.get("/verification-status/{application_id}")
def get_verification_status(application_id: str):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return {
        "success": True,
        "data": {
            "application_id": application_id,
            "identityConfig": build_identity_config(application),
            "identity_config": build_identity_config(application),
            "verification_status": application.get("verification_status", "not_started"),
            "aadhaarVerified": _is_aadhaar_verified(application),
            "aadhaar_verified": _is_aadhaar_verified(application),
            "governmentIdVerified": _is_aadhaar_verified(application),
            "government_id_verified": _is_aadhaar_verified(application),
            "faceVerified": _is_face_verified(application),
            "face_verified": _is_face_verified(application),
            "verification_completed": _is_verification_completed(application),
            "verification_timestamp": application.get("verification_timestamp"),
            "interview_status": application.get("interview_status", "not_started"),
        },
    }


@router.post("/verification/mark/{application_id}")
def mark_candidate_verified(application_id: str, payload: MarkVerifiedRequest):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Candidate not found")

    verified_at = _now_iso()
    attempts = max(1, int(payload.attempts or 1))
    matches = max(1, int(payload.matches or 1))
    identity_config = build_identity_config(application)
    face_source = _normalize_face_source(payload.reference_source, identity_config)
    government_id_required = requires_government_id(application)
    face_verification = {
        "source": face_source,
        "status": "passed",
        "score": payload.face_score,
        "attempts": attempts,
        "matches": matches,
        "required_matches": 1,
        "verifiedAt": verified_at,
        "verified_at": verified_at,
        "message": (
            "Candidate face matched resume photo"
            if face_source == RESUME_PHOTO_SOURCE
            else "Candidate face matched government ID photo"
        ),
    }
    updates = {
        "faceVerified": True,
        "face_verified": True,
        "faceVerificationAttempts": attempts,
        "faceVerificationMatches": matches,
        "faceVerificationRequiredMatches": 1,
        "faceVerificationScore": payload.face_score,
        "faceReferenceSource": face_source,
        "verificationStatus": "verified",
        "verification_status": "verified",
        "verification_completed": True,
        "verification_timestamp": verified_at,
        "faceVerification": face_verification,
        "face_verification": face_verification,
        "live_face_verification": face_verification,
    }

    if government_id_required:
        updates.update(
            {
                "aadhaarVerified": True,
                "aadhaar_verified": True,
                "governmentIdVerified": True,
                "government_id_verified": True,
            }
        )

    updated = update_application(
        application_id,
        updates,
    )

    if not updated:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return {
        "success": True,
        "data": {
            "application_id": application_id,
            "identityConfig": identity_config,
            "identity_config": identity_config,
            "verification_status": "verified",
            "aadhaarVerified": government_id_required,
            "faceVerified": True,
            "verification_completed": True,
            "next_step": "interview",
        },
    }


@router.post("/identity/upload/{application_id}")
@router.post("/aadhaar/upload/{application_id}")
async def upload_indian_government_id(application_id: str, aadhaar_file: UploadFile = File(...)):
    candidate_dir = None

    try:
        if not application_id:
            raise HTTPException(status_code=400, detail="Application ID is missing.")

        if not aadhaar_file:
            raise HTTPException(status_code=400, detail="Indian Government ID file is missing.")

        original_filename = aadhaar_file.filename or ""
        extension = Path(original_filename).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail="Only JPG, JPEG, PNG, or PDF Indian Government ID files are allowed.",
            )

        candidate_dir = CANDIDATE_STORAGE_DIR / application_id / "government_id"
        candidate_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = f"{uuid.uuid4()}_{Path(original_filename).name}"
        id_file_path = candidate_dir / safe_filename

        file_bytes = await aadhaar_file.read()

        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded Indian Government ID file is empty.")

        with open(id_file_path, "wb") as file:
            file.write(file_bytes)

        print("\n========== INDIAN GOVERNMENT ID UPLOAD ROUTE ==========")
        print("APPLICATION ID:", application_id)
        print("ID FILE:", id_file_path)
        print("FILE EXISTS:", id_file_path.exists())
        print("FILE SIZE:", id_file_path.stat().st_size)
        print("==========================================\n")

        result = verify_indian_id_for_application(
            application_id=application_id,
            id_file_path=str(id_file_path),
        )
        file_id = save_file_to_mongo(
            file_bytes,
            filename=Path(original_filename).name or safe_filename,
            content_type=aadhaar_file.content_type or "application/octet-stream",
            metadata={"application_id": application_id, "file_type": "government_id"},
        )
        _attach_identity_gridfs_files(application_id, result, file_id)

        status_code = result.get("status_code", 200)

        return _kyc_json_response(
            {
                "success": result.get("success", False),
                "message": result.get("message", "Indian Government ID verification completed."),
                "data": result.get("data", {}),
            },
            status_code=status_code,
        )

    except HTTPException as error:
        return _kyc_json_response(
            {
                "success": False,
                "message": error.detail,
                "data": {},
            },
            status_code=error.status_code,
        )

    except Exception as error:
        print("\n========== KYC ROUTE CRASH ==========")
        print(traceback.format_exc())
        print("=====================================\n")

        return _kyc_json_response(
            {
                "success": False,
                "message": "Indian Government ID verification failed. Please upload a clearer official ID.",
                "data": {
                    "error_type": type(error).__name__,
                    "next_step": "debug_backend",
                },
            },
            status_code=500,
        )
    finally:
        if candidate_dir:
            shutil.rmtree(candidate_dir, ignore_errors=True)


def _candidate_verification_payload(application: dict) -> dict:
    identity = application.get("identityVerification") or application.get("identity_verification") or {}
    aadhaar = application.get("aadhaar_verification") or application.get("kyc_verification") or identity or {}
    resume = application.get("resume") if isinstance(application.get("resume"), dict) else {}
    identity_config = build_identity_config(application)

    return {
        "application_id": application.get("application_id"),
        "candidate_name": application.get("candidate_name") or resume.get("candidate_name") or "",
        "email": application.get("email") or resume.get("email") or "",
        "ats_status": application.get("ats_status"),
        "identityConfig": identity_config,
        "identity_config": identity_config,
        "resumePhotoAvailable": identity_config["resumePhotoAvailable"],
        "resume_photo_available": identity_config["resumePhotoAvailable"],
        "verification_status": application.get("verification_status", "not_started"),
        "aadhaarVerified": _is_aadhaar_verified(application),
        "aadhaar_verified": _is_aadhaar_verified(application),
        "governmentIdVerified": _is_aadhaar_verified(application),
        "government_id_verified": _is_aadhaar_verified(application),
        "faceVerified": _is_face_verified(application),
        "face_verified": _is_face_verified(application),
        "verification_completed": _is_verification_completed(application),
        "verification_timestamp": application.get("verification_timestamp"),
        "aadhaar_verification": aadhaar,
        "identityVerification": identity,
        "identity_verification": identity,
        "documentType": identity.get("documentType") or identity.get("document_type") or application.get("documentType") or "aadhaar",
        "aadhaar_extracted_name": application.get("aadhaar_extracted_name") or aadhaar.get("extracted_name", ""),
        "aadhaar_face_image_available": bool(
            application.get("aadhaar_face_image_path")
            or aadhaar.get("aadhaar_face_image_path")
            or aadhaar.get("aadhaar_photo_path")
        ),
        "resume_face_image_available": bool(
            application.get("resume_face_image_path")
            or application.get("resume_photo_path")
            or resume.get("resume_face_image_path")
            or resume.get("resume_photo_path")
        ),
        "interview_status": application.get("interview_status", "not_started"),
        "interview_completed": application.get("interview_completed") is True,
    }


def _attach_identity_gridfs_files(application_id: str, result: dict, document_file_id: str) -> None:
    data = result.get("data") if isinstance(result, dict) else {}
    data = data if isinstance(data, dict) else {}
    identity = data.get("identityVerification") if isinstance(data.get("identityVerification"), dict) else {}
    photo_path = (
        data.get("aadhaar_face_image_path")
        or identity.get("aadhaar_face_image_path")
        or identity.get("aadhaar_photo_path")
        or identity.get("identity_photo_path")
    )
    photo_file_id = ""

    if photo_path and Path(str(photo_path)).exists():
        photo_file_id = save_path_to_mongo(
            photo_path,
            content_type="image/jpeg",
            metadata={"application_id": application_id, "file_type": "government_id_face"},
        )
        Path(str(photo_path)).unlink(missing_ok=True)

    gridfs_document_path = f"gridfs://{document_file_id}"
    gridfs_photo_path = f"gridfs://{photo_file_id}" if photo_file_id else ""
    updates = {
        "governmentIdFileId": document_file_id,
        "government_id_file_id": document_file_id,
        "government_id_image_path": gridfs_document_path,
        "aadhaar_image_path": gridfs_document_path,
    }

    if photo_file_id:
        updates.update(
            {
                "governmentIdPhotoFileId": photo_file_id,
                "government_id_photo_file_id": photo_file_id,
                "government_id_photo_path": gridfs_photo_path,
                "aadhaar_photo_path": gridfs_photo_path,
                "aadhaar_face_image_path": gridfs_photo_path,
            }
        )
        data["aadhaar_face_image_path"] = gridfs_photo_path
        data["aadhaar_photo_stored"] = True
        identity["photoFileId"] = photo_file_id
        identity["aadhaar_photo_path"] = gridfs_photo_path
        identity["aadhaar_face_image_path"] = gridfs_photo_path

    identity["documentFileId"] = document_file_id
    identity["document_file_id"] = document_file_id
    data["identityVerification"] = identity
    data["documentFileId"] = document_file_id
    updates["identityVerification"] = identity
    updates["identity_verification"] = identity
    update_application(application_id, updates)


def _is_verification_completed(application: dict) -> bool:
    return (
        application.get("verification_completed") is True
        or (_is_aadhaar_verified(application) and _is_face_verified(application))
        or str(application.get("verification_status") or "").lower() == "verified"
    )


def _is_aadhaar_verified(application: dict) -> bool:
    identity = application.get("identityVerification") or application.get("identity_verification") or {}
    explicit_government_id_passed = (
        application.get("aadhaarVerified") is True
        or application.get("aadhaar_verified") is True
        or application.get("governmentIdVerified") is True
        or application.get("government_id_verified") is True
        or identity.get("isValidIndianGovId") is True
        or identity.get("is_valid_indian_gov_id") is True
        or str(application.get("verification_status") or "").lower() in {"aadhaar_passed", "government_id_passed", "identity_passed"}
        or str(application.get("verificationStatus") or "").lower() in {"aadhaar_passed", "government_id_passed", "identity_passed"}
    )

    if not requires_government_id(application):
        return explicit_government_id_passed

    return (
        explicit_government_id_passed
        or str(application.get("verification_status") or "").lower() == "verified"
        or str(application.get("verificationStatus") or "").lower() == "verified"
    )


def _is_face_verified(application: dict) -> bool:
    live_face = application.get("live_face_verification")

    return (
        application.get("faceVerified") is True
        or application.get("face_verified") is True
        or (isinstance(live_face, dict) and str(live_face.get("status") or "").lower() == "passed")
    )


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _normalize_face_source(reference_source: str, identity_config: dict) -> str:
    source = str(reference_source or identity_config.get("faceVerificationSource") or "").strip().lower()

    if source in {"resume", "resume_face", "resume_photo"}:
        return RESUME_PHOTO_SOURCE

    return GOVERNMENT_ID_SOURCE
