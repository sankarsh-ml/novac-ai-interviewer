from pathlib import Path
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.db_service import MongoConnectionError, save_resume_application
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


async def _process_resume_upload(file: UploadFile):
    original_file_name = Path(file.filename or "").name

    if not original_file_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    RESUME_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    saved_file_name = f"{uuid.uuid4()}_{original_file_name}"
    saved_file_path = RESUME_STORAGE_DIR / saved_file_name

    file_content = await file.read()
    saved_file_path.write_bytes(file_content)

    try:
        extracted = extract_text_from_pdf(str(saved_file_path))
    except Exception as exc:
        saved_file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Unable to read the PDF file") from exc

    extracted_text = clean_text(extracted["text"])
    sections_detected = extract_sections(extracted_text)
    candidate_name = extract_candidate_name(extracted_text)
    resume_photo = extract_resume_photo(str(saved_file_path), str(RESUME_PHOTO_STORAGE_DIR / saved_file_name))

    return {
        "file_name": original_file_name,
        "saved_file_name": saved_file_name,
        "file_path": str(saved_file_path),
        "file_type": "pdf",
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
            "resume_photo_available": resume_photo["available"],
            "resume_photo_path": resume_photo["path"],
        },
    }


@router.post("/upload")
async def upload_resume(resume_file: UploadFile = File(...)):
    resume_data = await _process_resume_upload(resume_file)
    resume_summary = resume_data["resume"]

    try:
        application_id = save_resume_application(
            {
                **resume_data,
                "ats_status": "pending",
                "aadhaar_verification": _default_aadhaar_verification(),
            }
        )
    except MongoConnectionError as exc:
        raise HTTPException(
            status_code=500,
            detail="MongoDB connection failed. Make sure MongoDB is running.",
        ) from exc

    return {
        "success": True,
        "message": "Resume uploaded successfully",
        "data": {
            "application_id": application_id,
            "file_name": resume_data["file_name"],
            "resume_name": resume_summary["candidate_name"],
            "total_pages": resume_summary["total_pages"],
            "text_length": resume_summary["text_length"],
            "word_count": resume_summary["word_count"],
            "ats_status": "pending",
            "next_step": "ats_screening",
        },
    }


@router.post("/extract-text")
async def extract_resume_text(file: UploadFile = File(...)):
    resume_data = await _process_resume_upload(file)
    resume = resume_data["resume"]

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
        "name_match_score": None,
        "name_match_passed": False,
        "photo_match": {
            "status": "not_done",
            "score": None,
            "message": "",
        },
    }
