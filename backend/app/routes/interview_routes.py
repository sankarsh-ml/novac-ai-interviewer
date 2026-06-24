import traceback
import sys
import uuid
from pathlib import Path
import uuid
import json
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from app.services.whisper_service import transcribe_audio
from app.services.db_service import get_resume_application
from app.services.face_verification_service import (
    DEFAULT_FACE_VERIFY_THRESHOLD,
    get_dependency_status,
    get_face_app,
    verify_faces,
)


router = APIRouter()

APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
LIVE_FRAME_DIR = APP_DIR / "storage" / "live_frames"
LIVE_FRAME_DIR.mkdir(parents=True, exist_ok=True)
INTERVIEW_AUDIO_DIR = APP_DIR / "storage" / "interview_audio"
INTERVIEW_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
TEXT_DIR = APP_DIR / "storage" / "text"
TEXT_DIR.mkdir(parents=True, exist_ok=True)
APP_DIR = Path(__file__).resolve().parent.parent

INTERVIEW_LINK_DIR = (APP_DIR /"storage" /"interview_links")

INTERVIEW_LINK_DIR.mkdir(parents=True,exist_ok=True)
APPLICATIONS_FILE = (APP_DIR /"storage" /"applications.json")

def update_application_link(application_id,interview_link,expiry_date):

    with open(APPLICATIONS_FILE,"r") as file:

        applications =json.load(file)

    for application in applications:

        if (
            application[
                "application_id"
            ]
            ==
            application_id
        ):

            application[
                "interview_link"
            ] = interview_link

            application[
                "expiry_date"
            ] = expiry_date

            break

    with open(
        APPLICATIONS_FILE,
        "w"
    ) as file:

        json.dump(
            applications,
            file,
            indent=4
        )

@router.post("/create-link")
async def create_link(payload: dict):
    print("CREATE LINK API HIT")
    token = uuid.uuid4().hex
    link = (f"http://localhost:5173/interview/{token}")
    data = {
        "token": token,
        "application_id":
            payload["application_id"],
        "candidate_name":
            payload["candidate_name"],
        "email":
            payload["email"],
        "expiry_date":
            payload["expiry_date"],
        "used": False,
        "link": link
    }
    file_path = (INTERVIEW_LINK_DIR /f"{token}.json")
    print("INTERVIEW_LINK_DIR =", INTERVIEW_LINK_DIR)
    print("FILE PATH =", file_path)
    with open(file_path,"w") as file:

        json.dump(data,file,indent=4)
    
    update_application_link(payload["application_id"],link,payload["expiry_date"])
    return {
    "success": True,
    "link": link
}

@router.get("/validate-token/{token}")
def validate_token(token: str):

    file_path = (
        INTERVIEW_LINK_DIR /
        f"{token}.json"
    )

    if not file_path.exists():

        return {
            "success": False,
            "message":
                "Invalid Interview Link"
        }

    try:

        with open(
            file_path,
            "r"
        ) as file:

            data = json.load(file)

        if data.get("used", False):

            return {
                "success": False,
                "message":
                    "Interview Already Completed"
            }

        expiry_date = datetime.fromisoformat(
            data["expiry_date"]
        )

        if datetime.now() > expiry_date:

            return {
                "success": False,
                "message":
                    "Interview Link Expired"
            }

        return {
            "success": True,
            "message":
                "Interview Link Valid",

            "application_id":
                data["application_id"],

            "candidate_name":
                data["candidate_name"],

            "email":
                data["email"],

            "expiry_date":
                data["expiry_date"]
        }

    except Exception as error:

        return {
            "success": False,
            "message":
                f"Validation Error: {str(error)}"
        }

@router.post("/face-verify/{application_id}")
async def face_verify(application_id: str, frame: UploadFile = File(...)):
    live_frame_path = None

    try:
        print(f"[Interview face-verify] application_id={application_id}")
        application = get_resume_application(application_id)

        if not application:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "match": False,
                    "score": 0.0,
                    "threshold": DEFAULT_FACE_VERIFY_THRESHOLD,
                    "message": "Resume application not found",
                },
            )

        reference_path, reference_source, checked_paths = _find_reference_face_path(application)
        print(f"[Interview face-verify] reference_source={reference_source}")
        print(f"[Interview face-verify] reference_path={reference_path}")
        print(
            "[Interview face-verify] reference_path_exists="
            f"{bool(reference_path and Path(reference_path).exists())}"
        )

        if not reference_path:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "match": False,
                    "score": 0.0,
                    "threshold": DEFAULT_FACE_VERIFY_THRESHOLD,
                    "message": "No reference face available from resume or Aadhaar",
                    "checked_paths": checked_paths,
                },
            )

        file_bytes = await frame.read()

        if not file_bytes:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "match": False,
                    "score": 0.0,
                    "threshold": DEFAULT_FACE_VERIFY_THRESHOLD,
                    "reference_source": reference_source,
                    "message": "Uploaded live frame is empty",
                },
            )

        live_frame_path = LIVE_FRAME_DIR / f"{uuid.uuid4()}.jpg"
        live_frame_path.write_bytes(file_bytes)
        print(f"[Interview face-verify] saved_live_frame_path={live_frame_path}")

        result = verify_faces(
            str(reference_path),
            str(live_frame_path),
            threshold=DEFAULT_FACE_VERIFY_THRESHOLD,
        )
        result["reference_source"] = reference_source
        print(f"[Interview face-verify] face_verification_result={result}")

        return JSONResponse(status_code=200, content=result)

    except Exception as error:
        print("\n========== INTERVIEW FACE VERIFY CRASH ==========")
        print(traceback.format_exc())
        print("=================================================\n")

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "match": False,
                "score": 0.0,
                "threshold": DEFAULT_FACE_VERIFY_THRESHOLD,
                "message": f"Face verification failed: {str(error)}",
            },
        )

@router.post("/upload-audio/{application_id}")
async def upload_interview_audio(
    application_id: str,
    audio: UploadFile = File(...)
):
    try:

        audio_bytes = await audio.read()

        if not audio_bytes:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "Empty audio file"
                }
            )

        audio_path = (
            INTERVIEW_AUDIO_DIR /
            f"{application_id}.webm"
        )

        audio_path.write_bytes(audio_bytes)

        print(f"[Interview Audio] Saved: {audio_path}")
        
        print("[Whisper] Starting transcription...")

        transcript = transcribe_audio(str(audio_path))

        print("[Whisper] Transcription complete")
        
        transcript_path = (TEXT_DIR /f"{application_id}.txt")

        transcript_path.write_text(transcript,encoding="utf-8")

        print(f"[Whisper] Transcript saved: {transcript_path}")

        return JSONResponse(
    status_code=200,
    content={"success": True,"message": "Audio saved and transcribed","transcript": transcript})

    except Exception as error:
        print(traceback.format_exc())

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": str(error)
            }
        )


@router.get("/face-health")
def face_health():
    dependencies, dependency_errors = get_dependency_status()
    response = {
        "success": False,
        "python": sys.executable,
        "dependencies": dependencies,
        "face_app": "not_checked",
    }

    try:
        get_face_app()
        response["face_app"] = "initialized"
    except Exception as error:
        response["face_app"] = "failed"
        response["error"] = str(error)

    if dependency_errors and "error" not in response:
        response["error"] = "; ".join(
            f"{name}: {message}" for name, message in dependency_errors.items()
        )

    response["success"] = (
        all(status == "ok" for status in dependencies.values())
        and response["face_app"] == "initialized"
    )

    return JSONResponse(status_code=200, content=response)


def _find_reference_face_path(application: dict):
    resume_candidates = [
        application.get("resume_photo_path"),
        _safe_get(application, ["resume", "photo_path"]),
        _safe_get(application, ["resume", "face_path"]),
        _safe_get(application, ["resume", "image_path"]),
        _safe_get(application, ["resume", "resume_photo_path"]),
    ]

    aadhaar_candidates = [
        application.get("aadhaar_photo_path"),
        _safe_get(application, ["kyc", "aadhaar_photo_path"]),
        _safe_get(application, ["kyc", "photo_path"]),
        _safe_get(application, ["aadhaar", "photo_path"]),
        _safe_get(application, ["kyc_verification", "aadhaar_photo_path"]),
        _safe_get(application, ["aadhaar_verification", "aadhaar_photo_path"]),
    ]

    checked_paths = []

    for candidate in resume_candidates:
        resolved_path = _existing_path(candidate, checked_paths, "resume")

        if resolved_path:
            return resolved_path, "resume", checked_paths

    for candidate in aadhaar_candidates:
        resolved_path = _existing_path(candidate, checked_paths, "aadhaar")

        if resolved_path:
            return resolved_path, "aadhaar", checked_paths

    return None, None, checked_paths


def _safe_get(mapping: dict, keys: list[str]):
    current = mapping

    for key in keys:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def _existing_path(path_value, checked_paths=None, source=None):
    if not path_value:
        return None

    candidate = Path(str(path_value)).expanduser()

    if candidate.exists():
        _record_checked_path(checked_paths, source, path_value, candidate, True)
        return candidate

    relative_candidate = PROJECT_ROOT / candidate

    if relative_candidate.exists():
        _record_checked_path(checked_paths, source, path_value, relative_candidate, True)
        return relative_candidate

    app_relative_candidate = APP_DIR / candidate

    if app_relative_candidate.exists():
        _record_checked_path(checked_paths, source, path_value, app_relative_candidate, True)
        return app_relative_candidate

    _record_checked_path(checked_paths, source, path_value, candidate, False)
    return None


def _record_checked_path(checked_paths, source, original_path, resolved_path, exists):
    if checked_paths is None:
        return

    checked_paths.append(
        {
            "source": source,
            "path": str(original_path),
            "resolved_path": str(resolved_path),
            "exists": exists,
        }
    )
