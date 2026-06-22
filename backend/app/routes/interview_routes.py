import traceback
import sys
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.answer_evaluation_service import evaluate_answer_with_qwen
from app.services.db_service import get_resume_application, update_application
from app.services.face_verification_service import (
    DEFAULT_FACE_VERIFY_THRESHOLD,
    get_dependency_status,
    get_face_app,
    verify_faces,
)
from app.services.question_generation_service import generate_interview_questions
from app.services.qwen_service import is_qwen_available


router = APIRouter()

APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
LIVE_FRAME_DIR = APP_DIR / "storage" / "live_frames"
LIVE_FRAME_DIR.mkdir(parents=True, exist_ok=True)


class AnswerEvaluationRequest(BaseModel):
    question_id: str
    answer_text: str


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


@router.get("/qwen-health")
def qwen_health():
    result = is_qwen_available()

    if result.get("success"):
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "qwen_available": True,
                "model": result.get("model"),
                "base_url": result.get("base_url"),
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "success": False,
            "qwen_available": False,
            "message": result.get("message", "Qwen unavailable"),
            "model": result.get("model"),
            "base_url": result.get("base_url"),
        },
    )


@router.get("/questions/{application_id}")
def get_interview_questions(application_id: str):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    existing_questions = application.get("interview_questions")

    if isinstance(existing_questions, dict) and _has_current_question_contract(existing_questions):
        return existing_questions

    result = generate_interview_questions(application)
    update_application(application_id, {"interview_questions": result})
    return result


@router.post("/questions/{application_id}/regenerate")
def regenerate_interview_questions(application_id: str):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    result = generate_interview_questions(application)
    update_application(application_id, {"interview_questions": result})
    return result


@router.post("/questions/{application_id}/evaluate")
def evaluate_interview_answer(application_id: str, request: AnswerEvaluationRequest):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    question = _find_question(application, request.question_id)

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    evaluation = evaluate_answer_with_qwen(application, question, request.answer_text)
    answer_record = {
        "question_id": request.question_id,
        "answer_text": request.answer_text,
        "evaluation": evaluation,
    }

    interview_answers = application.get("interview_answers")

    if not isinstance(interview_answers, dict):
        interview_answers = {}

    interview_answers[request.question_id] = answer_record
    update_application(application_id, {"interview_answers": interview_answers})

    return evaluation


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


def _find_question(application: dict, question_id: str) -> dict | None:
    question_payload = application.get("interview_questions") or {}
    questions = question_payload.get("questions") if isinstance(question_payload, dict) else []

    if not isinstance(questions, list):
        return None

    for question in questions:
        if isinstance(question, dict) and str(question.get("id")) == str(question_id):
            return question

    return None


def _has_current_question_contract(question_payload: dict) -> bool:
    questions = question_payload.get("questions")

    if not isinstance(questions, list) or len(questions) != 5:
        return False

    difficulty_counts = {"Easy": 0, "Medium": 0, "Hard": 0}

    for index, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            return False

        if question.get("id") != f"q{index}":
            return False

        difficulty = question.get("difficulty")

        if difficulty not in difficulty_counts:
            return False

        difficulty_counts[difficulty] += 1

    return difficulty_counts == {"Easy": 2, "Medium": 2, "Hard": 1}
