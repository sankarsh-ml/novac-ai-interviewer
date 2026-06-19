from pathlib import Path
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.resume_parser import (
    clean_text,
    extract_sections,
    extract_text_from_pdf,
)


router = APIRouter(prefix="/api/resume", tags=["Resume"])

APP_DIR = Path(__file__).resolve().parents[1]
RESUME_STORAGE_DIR = APP_DIR / "storage" / "resumes"


@router.post("/extract-text")
async def extract_resume_text(file: UploadFile = File(...)):
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

    return {
        "success": True,
        "message": "Resume text extracted successfully",
        "data": {
            "file_name": original_file_name,
            "saved_file_name": saved_file_name,
            "file_type": "pdf",
            "total_pages": extracted["total_pages"],
            "text_length": len(extracted_text),
            "word_count": len(extracted_text.split()),
            "extracted_text": extracted_text,
            "ats_ready_data": {
                "raw_text": extracted_text,
                "normalized_text": extracted_text,
                "sections_detected": sections_detected,
            },
        },
    }
