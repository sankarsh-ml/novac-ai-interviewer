import os
import traceback
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.db_service import get_resume_application, update_application
from app.services.kyc_service import verify_aadhaar_for_application


router = APIRouter()

APP_DIR = Path(__file__).resolve().parents[1]
AADHAAR_UPLOAD_DIR = APP_DIR / "storage" / "aadhaar"
AADHAAR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CANDIDATE_STORAGE_DIR = APP_DIR / "storage" / "candidates"

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}


class MarkVerifiedRequest(BaseModel):
    reference_source: str = ""
    face_score: float | None = None
    attempts: int = 1
    matches: int = 1


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
            "verification_status": application.get("verification_status", "not_started"),
            "aadhaarVerified": _is_aadhaar_verified(application),
            "aadhaar_verified": _is_aadhaar_verified(application),
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
    updated = update_application(
        application_id,
        {
            "aadhaarVerified": True,
            "aadhaar_verified": True,
            "faceVerified": True,
            "face_verified": True,
            "faceVerificationAttempts": attempts,
            "faceVerificationMatches": matches,
            "faceVerificationRequiredMatches": 1,
            "faceVerificationScore": payload.face_score,
            "faceReferenceSource": payload.reference_source,
            "verificationStatus": "verified",
            "verification_status": "verified",
            "verification_completed": True,
            "verification_timestamp": verified_at,
            "live_face_verification": {
                "status": "passed",
                "reference_source": payload.reference_source,
                "score": payload.face_score,
                "attempts": attempts,
                "matches": matches,
                "required_matches": 1,
                "verified_at": verified_at,
            },
        },
    )

    if not updated:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return {
        "success": True,
        "data": {
            "application_id": application_id,
            "verification_status": "verified",
            "aadhaarVerified": True,
            "faceVerified": True,
            "verification_completed": True,
            "next_step": "interview",
        },
    }


@router.post("/aadhaar/upload/{application_id}")
async def upload_aadhaar(application_id: str, aadhaar_file: UploadFile = File(...)):
    try:
        if not application_id:
            raise HTTPException(status_code=400, detail="Application ID is missing.")

        if not aadhaar_file:
            raise HTTPException(status_code=400, detail="Aadhaar file is missing.")

        original_filename = aadhaar_file.filename or ""
        extension = Path(original_filename).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail="Only JPG, JPEG, PNG, or PDF Aadhaar files are allowed.",
            )

        candidate_dir = CANDIDATE_STORAGE_DIR / application_id / "aadhaar"
        candidate_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = f"{uuid.uuid4()}_{Path(original_filename).name}"
        aadhaar_file_path = candidate_dir / safe_filename

        file_bytes = await aadhaar_file.read()

        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded Aadhaar file is empty.")

        with open(aadhaar_file_path, "wb") as file:
            file.write(file_bytes)

        print("\n========== AADHAAR UPLOAD ROUTE ==========")
        print("APPLICATION ID:", application_id)
        print("AADHAAR FILE:", aadhaar_file_path)
        print("FILE EXISTS:", aadhaar_file_path.exists())
        print("FILE SIZE:", aadhaar_file_path.stat().st_size)
        print("==========================================\n")

        result = verify_aadhaar_for_application(
            application_id=application_id,
            aadhaar_file_path=str(aadhaar_file_path),
        )

        status_code = result.get("status_code", 200)

        return JSONResponse(
            status_code=status_code,
            content={
                "success": result.get("success", False),
                "message": result.get("message", "Aadhaar verification completed."),
                "data": result.get("data", {}),
            },
        )

    except HTTPException as error:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "success": False,
                "message": error.detail,
                "data": {},
            },
        )

    except Exception as error:
        print("\n========== KYC ROUTE CRASH ==========")
        print(traceback.format_exc())
        print("=====================================\n")

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"KYC backend crashed: {str(error)}",
                "data": {
                    "error_type": type(error).__name__,
                    "next_step": "debug_backend",
                },
            },
        )


def _candidate_verification_payload(application: dict) -> dict:
    aadhaar = application.get("aadhaar_verification") or application.get("kyc_verification") or {}
    resume = application.get("resume") if isinstance(application.get("resume"), dict) else {}

    return {
        "application_id": application.get("application_id"),
        "candidate_name": application.get("candidate_name") or resume.get("candidate_name") or "",
        "email": application.get("email") or resume.get("email") or "",
        "ats_status": application.get("ats_status"),
        "verification_status": application.get("verification_status", "not_started"),
        "aadhaarVerified": _is_aadhaar_verified(application),
        "aadhaar_verified": _is_aadhaar_verified(application),
        "faceVerified": _is_face_verified(application),
        "face_verified": _is_face_verified(application),
        "verification_completed": _is_verification_completed(application),
        "verification_timestamp": application.get("verification_timestamp"),
        "aadhaar_verification": aadhaar,
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


def _is_verification_completed(application: dict) -> bool:
    return (
        application.get("verification_completed") is True
        or (_is_aadhaar_verified(application) and _is_face_verified(application))
        or str(application.get("verification_status") or "").lower() == "verified"
    )


def _is_aadhaar_verified(application: dict) -> bool:
    return (
        application.get("aadhaarVerified") is True
        or application.get("aadhaar_verified") is True
        or str(application.get("verification_status") or "").lower() in {"aadhaar_passed", "verified"}
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
