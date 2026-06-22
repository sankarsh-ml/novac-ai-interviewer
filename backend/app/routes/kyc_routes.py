import os
import traceback
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.services.kyc_service import verify_aadhaar_for_application


router = APIRouter()

APP_DIR = Path(__file__).resolve().parents[1]
AADHAAR_UPLOAD_DIR = APP_DIR / "storage" / "aadhaar"
AADHAAR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}


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

        safe_filename = f"{uuid.uuid4()}_{Path(original_filename).name}"
        aadhaar_file_path = AADHAAR_UPLOAD_DIR / safe_filename

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