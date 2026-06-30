from pathlib import Path
from typing import Optional
import hashlib
import re
import shutil
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.routes.ats_routes import score_resume
from app.services.file_storage_service import save_file_to_mongo, save_path_to_mongo
from app.services.db_service import get_application_by_id, list_applications, save_resume_application
from app.services.resume_parser import (
    clean_text,
    extract_candidate_name,
    extract_resume_photo,
    extract_sections,
    extract_text_from_pdf,
)


router = APIRouter()

APP_DIR = Path(__file__).resolve().parents[1]
RESUME_STORAGE_DIR = APP_DIR / "storage" / "resumes"
RESUME_PHOTO_STORAGE_DIR = APP_DIR / "storage" / "resume_photos"
CANDIDATE_STORAGE_DIR = APP_DIR / "storage" / "candidates"


def extract_email(text: str) -> str:
    match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return match.group(0) if match else ""


async def _process_resume_upload(file: UploadFile, application_id: str | None = None):
    original_file_name = Path(file.filename or "").name

    if not original_file_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    if application_id:
        resume_storage_dir = CANDIDATE_STORAGE_DIR / application_id / "resumes"
        resume_photo_storage_dir = CANDIDATE_STORAGE_DIR / application_id / "resume_faces"
    else:
        resume_storage_dir = RESUME_STORAGE_DIR
        resume_photo_storage_dir = RESUME_PHOTO_STORAGE_DIR

    resume_storage_dir.mkdir(parents=True, exist_ok=True)

    saved_file_name = f"{uuid.uuid4()}_{original_file_name}"
    saved_file_path = resume_storage_dir / saved_file_name

    file_content = await file.read()
    file_hash = hashlib.sha256(file_content).hexdigest()
    saved_file_path.write_bytes(file_content)

    try:
        extracted = extract_text_from_pdf(str(saved_file_path))
    except Exception as exc:
        saved_file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Unable to read the PDF file") from exc

    extracted_text = clean_text(extracted["text"])
    sections_detected = extract_sections(extracted_text)
    candidate_name = extract_candidate_name(extracted_text)
    email = extract_email(extracted_text)
    resume_photo = extract_resume_photo(str(saved_file_path), str(resume_photo_storage_dir))
    resume_photo_path = resume_photo["path"] or None

    return {
        "application_id": application_id,
        "file_name": original_file_name,
        "saved_file_name": saved_file_name,
        "file_path": str(saved_file_path),
        "file_content": file_content,
        "file_type": "pdf",
        "resume_file_hash": file_hash,
        "processing_status": "processed",
        "resume": {
            "total_pages": extracted["total_pages"],
            "text_length": len(extracted_text),
            "word_count": len(extracted_text.split()),
            "extracted_text": extracted_text,
            "ats_ready_data": {
                "raw_text": extracted_text,
                "normalized_text": extracted_text,
                "sections_detected": sections_detected,
            },
            "candidate_name": candidate_name,
            "email": email,
            "resume_photo_available": resume_photo["available"],
            "resume_photo_path": resume_photo_path,
            "resume_face_image_path": resume_photo_path,
        },
    }


@router.post("/bulk-upload")
async def bulk_upload_resumes(
    job_id: str = Form(...),
    resumes: list[UploadFile] = File(...),
):
    processed = []
    failed = []

    for resume_file in resumes:
        try:
            result = await _save_resume_application_for_file(resume_file, job_id)

            if not result.get("duplicate"):
                try:
                    score_resume(result["application_id"])
                except HTTPException as exc:
                    result["processing_status"] = "ats_failed"
                    result["error"] = str(exc.detail)

            application = get_application_by_id(result["application_id"]) or {}
            processed.append(
                {
                    "application_id": result["application_id"],
                    "candidate_name": application.get("candidate_name") or result.get("candidate_name"),
                    "email": application.get("email") or result.get("email"),
                    "file_name": result.get("file_name"),
                    "ats_status": application.get("ats_status") or result.get("ats_status"),
                    "ats_score": application.get("ats_score"),
                    "processing_status": result.get("processing_status", application.get("processing_status")),
                    "duplicate": result.get("duplicate", False),
                    **({"error": result["error"]} if result.get("error") else {}),
                }
            )
        except HTTPException as exc:
            failed.append(
                {
                    "file_name": Path(resume_file.filename or "").name,
                    "error": str(exc.detail),
                }
            )
        except Exception as exc:
            failed.append(
                {
                    "file_name": Path(resume_file.filename or "").name,
                    "error": str(exc),
                }
            )

    return {
        "success": len(processed) > 0 and len(failed) == 0,
        "partial_success": len(processed) > 0 and len(failed) > 0,
        "count": len(processed),
        "failed_count": len(failed),
        "applications": processed,
        "failed": failed,
    }


@router.post("/upload")
async def upload_resume(
    resume_file: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
    job_id: str | None = Form(None),
):
    upload_file = resume_file or file

    if not upload_file:
        raise HTTPException(status_code=400, detail="Resume file is required")

    result = await _save_resume_application_for_file(upload_file, job_id)

    return {
        "success": True,
        "message": "Resume already exists" if result.get("duplicate") else "Resume uploaded successfully",
        "data": {
            "application_id": result["application_id"],
            "file_name": result["file_name"],
            "job_id": job_id,
            "resume_name": result["candidate_name"],
            "email": result.get("email"),
            "total_pages": result["total_pages"],
            "text_length": result["text_length"],
            "word_count": result["word_count"],
            "ats_status": result["ats_status"],
            "processing_status": result["processing_status"],
            "duplicate": result.get("duplicate", False),
            "next_step": "ats_screening",
        },
    }


@router.post("/extract-text")
async def extract_resume_text(file: UploadFile = File(...)):
    resume_data = await _process_resume_upload(file)
    resume = resume_data["resume"]

    try:
        return {
            "success": True,
            "message": "Resume text extracted successfully",
            "data": {
                "file_name": resume_data["file_name"],
                "saved_file_name": resume_data["saved_file_name"],
                "file_type": resume_data["file_type"],
                "total_pages": resume["total_pages"],
                "text_length": resume["text_length"],
                "word_count": resume["word_count"],
                "extracted_text": resume["extracted_text"],
                "ats_ready_data": resume["ats_ready_data"],
            },
        }
    finally:
        _cleanup_resume_processing_files(resume_data)


def _default_aadhaar_verification():
    return {
        "verification_status": "not_started",
        "aadhaar_detected": False,
        "aadhaar_confidence": None,
        "extracted_name": "",
        "masked_aadhaar_number": "",
        "dob": "",
        "gender": "",
        "aadhaar_photo_path": "",
        "aadhaar_face_image_path": "",
        "name_match_score": None,
        "name_match_passed": False,
        "photo_match": {
            "status": "not_done",
            "score": None,
            "message": "",
        },
    }


async def _save_resume_application_for_file(upload_file: UploadFile, job_id: str | None):
    application_id = str(uuid.uuid4())
    resume_data = await _process_resume_upload(upload_file, application_id=application_id)
    resume_summary = resume_data["resume"]
    duplicate_application = _find_duplicate_application(resume_data["resume_file_hash"], job_id)

    if duplicate_application:
        Path(resume_data["file_path"]).unlink(missing_ok=True)
        resume_photo_path = resume_summary.get("resume_photo_path")

        if resume_photo_path:
            Path(resume_photo_path).unlink(missing_ok=True)

        if application_id:
            shutil.rmtree(CANDIDATE_STORAGE_DIR / application_id, ignore_errors=True)

        return _application_result(duplicate_application, duplicate=True)

    resume_file_id = save_file_to_mongo(
        resume_data.pop("file_content"),
        filename=resume_data["file_name"],
        content_type="application/pdf",
        metadata={"application_id": application_id, "job_id": job_id, "file_type": "resume"},
    )
    resume_photo_file_id = ""
    resume_photo_path = resume_summary.get("resume_photo_path")

    if resume_photo_path and Path(resume_photo_path).exists():
        resume_photo_file_id = save_path_to_mongo(
            resume_photo_path,
            content_type="image/jpeg",
            metadata={"application_id": application_id, "job_id": job_id, "file_type": "resume_face"},
        )

    saved_application_id = save_resume_application(
        {
            **resume_data,
            "application_id": application_id,
            "job_id": job_id,
            "resumeFileId": resume_file_id,
            "resume_file_id": resume_file_id,
            "file_path": f"gridfs://{resume_file_id}",
            "ats_ready_data": resume_summary["ats_ready_data"],
            "candidate_name": resume_summary["candidate_name"],
            "email": resume_summary["email"],
            "resumePhotoFileId": resume_photo_file_id,
            "resume_photo_file_id": resume_photo_file_id,
            "resume_photo_path": f"gridfs://{resume_photo_file_id}" if resume_photo_file_id else "",
            "resume_face_image_path": f"gridfs://{resume_photo_file_id}" if resume_photo_file_id else "",
            "candidate_image_path": f"gridfs://{resume_photo_file_id}" if resume_photo_file_id else "",
            "candidate_folder": "",
            "ats_status": "pending",
            "verification_status": "not_started",
            "verification_completed": False,
            "aadhaarVerified": False,
            "aadhaar_verified": False,
            "faceVerified": False,
            "face_verified": False,
            "faceVerificationAttempts": 0,
            "faceVerificationMatches": 0,
            "faceVerificationRequiredMatches": 1,
            "interview_status": "not_started",
            "interview_completed": False,
            "interview_answers": {},
            "aadhaar_verification": _default_aadhaar_verification(),
            "kyc_verification": _default_aadhaar_verification(),
        }
    )

    shutil.rmtree(CANDIDATE_STORAGE_DIR / application_id, ignore_errors=True)
    application = get_application_by_id(saved_application_id) or {}
    return _application_result(application, duplicate=False)


def _cleanup_resume_processing_files(resume_data: dict) -> None:
    file_path = resume_data.get("file_path")
    resume = resume_data.get("resume") if isinstance(resume_data.get("resume"), dict) else {}
    photo_path = resume.get("resume_photo_path")

    if file_path:
        Path(file_path).unlink(missing_ok=True)

    if photo_path:
        Path(photo_path).unlink(missing_ok=True)


def _find_duplicate_application(file_hash: str, job_id: str | None) -> dict | None:
    for application in list_applications():
        if application.get("resume_file_hash") != file_hash:
            continue

        if str(application.get("job_id") or "") == str(job_id or ""):
            return application

    return None


def _application_result(application: dict, duplicate: bool) -> dict:
    resume = application.get("resume", {}) if isinstance(application.get("resume"), dict) else {}

    return {
        "application_id": application.get("application_id"),
        "file_name": application.get("file_name"),
        "candidate_name": application.get("candidate_name") or resume.get("candidate_name"),
        "email": application.get("email") or resume.get("email"),
        "total_pages": resume.get("total_pages", 0),
        "text_length": resume.get("text_length", 0),
        "word_count": resume.get("word_count", 0),
        "ats_status": application.get("ats_status", "pending"),
        "processing_status": application.get("processing_status", "processed"),
        "duplicate": duplicate,
    }
