import traceback
import sys
import uuid
import json
import os
from pathlib import Path
from datetime import datetime, timedelta

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.answer_evaluation_service import evaluate_answer_with_qwen, normalize_score
from app.services.db_service import get_resume_application, update_application
from app.services.face_verification_service import (
    DEFAULT_FACE_VERIFY_THRESHOLD,
    get_dependency_status,
    get_face_app,
    verify_faces,
)
from app.services.question_generation_service import generate_interview_questions
from app.services.question_bank_service import load_question_bank
from app.services.qwen_service import is_qwen_available
from app.services.whisper_service import transcribe_audio


router = APIRouter()

APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
LIVE_FRAME_DIR = APP_DIR / "storage" / "live_frames"
LIVE_FRAME_DIR.mkdir(parents=True, exist_ok=True)
INTERVIEW_LINK_DIR = APP_DIR / "storage" / "interview_links"
INTERVIEW_LINK_DIR.mkdir(parents=True, exist_ok=True)
CANDIDATE_STORAGE_DIR = APP_DIR / "storage" / "candidates"


class AnswerEvaluationRequest(BaseModel):
    question_id: str
    answer_text: str
    transcript: str = ""
    audio_path: str = ""


class CreateInterviewLinkRequest(BaseModel):
    application_id: str
    candidate_name: str = ""
    email: str = ""
    expiry_date: str | None = None


@router.post("/create-link")
def create_interview_link(payload: CreateInterviewLinkRequest):
    application = get_resume_application(payload.application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if _is_interview_completed(application):
        raise HTTPException(status_code=400, detail="Interview already completed")

    token = uuid.uuid4().hex
    expiry_date = _normalize_expiry_date(payload.expiry_date)
    frontend_base_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
    verification_url = f"{frontend_base_url}/verify/{payload.application_id}"
    interview_url = f"{frontend_base_url}/interview/{payload.application_id}"
    data = {
        "token": token,
        "application_id": payload.application_id,
        "candidate_name": payload.candidate_name or _get_candidate_name(application),
        "email": payload.email or application.get("email", ""),
        "expiry_date": expiry_date,
        "used": False,
        "link": verification_url,
        "verification_url": verification_url,
        "interview_url": interview_url,
    }

    (INTERVIEW_LINK_DIR / f"{token}.json").write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )
    update_application(
        payload.application_id,
        {
            "interview_link": verification_url,
            "verification_link": verification_url,
            "interview_token": token,
            "expiry_date": expiry_date,
            "interview_status": application.get("interview_status") or "link_created",
        },
    )

    return {
        "success": True,
        "link": verification_url,
        "verificationUrl": verification_url,
        "verification_url": verification_url,
        "interviewUrl": interview_url,
        "interview_url": interview_url,
        "token": token,
        "expiry_date": expiry_date,
    }


@router.get("/validate-token/{token}")
def validate_token(token: str):
    link_data = _load_link_data(token)

    if not link_data:
        return {
            "success": False,
            "message": "Invalid Interview Link",
        }

    application = get_resume_application(link_data.get("application_id"))

    if not application:
        return {
            "success": False,
            "message": "Application not found",
        }

    if link_data.get("used") or _is_interview_completed(application):
        return {
            "success": False,
            "message": "Interview Already Completed",
        }

    try:
        expiry_date = datetime.fromisoformat(str(link_data["expiry_date"]))
    except Exception:
        expiry_date = datetime.now() - timedelta(seconds=1)

    if datetime.now() > expiry_date:
        return {
            "success": False,
            "message": "Interview Link Expired",
        }

    return {
        "success": True,
        "message": "Interview Link Valid",
        "application_id": link_data["application_id"],
        "candidate_name": link_data.get("candidate_name") or _get_candidate_name(application),
        "email": link_data.get("email") or application.get("email", ""),
        "expiry_date": link_data["expiry_date"],
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

    if not _is_interview_access_verified(application):
        raise HTTPException(status_code=403, detail="Candidate verification is required before interview")

    return _prepare_interview_questions(application_id, application)


@router.get("/{application_id}/questions")
def get_candidate_interview_questions(application_id: str):
    return get_interview_questions(application_id)


@router.post("/{application_id}/start")
def start_interview(application_id: str):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if not _is_interview_access_verified(application):
        raise HTTPException(status_code=403, detail="Aadhaar and face verification are required before interview")

    if _is_interview_completed(application):
        return {
            "success": True,
            "status": "completed",
            "interview_status": "completed",
            "interviewStatus": "completed",
            "interview_completed": True,
            "questions": [],
            "message": "Interview already completed",
        }

    questions = _prepare_interview_questions(application_id, application)
    update_application(
        application_id,
        {
            "interview_status": "in_progress",
            "interviewStatus": "in_progress",
            "interview_completed": False,
        },
    )

    return {
        **questions,
        "interview_status": "in_progress",
        "interviewStatus": "in_progress",
    }


@router.post("/questions/{application_id}/regenerate")
def regenerate_interview_questions(application_id: str):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if not _is_interview_access_verified(application):
        raise HTTPException(status_code=403, detail="Candidate verification is required before interview")

    result = generate_interview_questions(application)

    if not result.get("success"):
        raise HTTPException(status_code=503, detail=result.get("message") or "Could not prepare interview questions")

    update_application(
        application_id,
        {
            "interview_questions": result,
            "question_source": result.get("question_source") or result.get("source"),
            "question_bank_id": result.get("question_bank_id", application.get("question_bank_id")),
            "question_bank_name": result.get("question_bank_name", application.get("question_bank_name")),
        },
    )
    return result


@router.post("/{application_id}/transcribe")
async def transcribe_interview_audio(application_id: str, audio: UploadFile = File(...)):
    print(f"[Interview transcribe] audio received application_id={application_id} filename={audio.filename}")
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if not _is_interview_access_verified(application):
        raise HTTPException(status_code=403, detail="Candidate verification is required before interview")

    audio_bytes = await audio.read()

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Uploaded audio is empty")

    audio_dir = _candidate_folder(application, application_id) / "interview_audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    extension = _safe_audio_extension(audio.filename)
    audio_path = audio_dir / f"{uuid.uuid4().hex}{extension}"
    audio_path.write_bytes(audio_bytes)
    print(f"[Interview transcribe] audio saved path={audio_path}")

    result = transcribe_audio(audio_path)

    if not result.get("success"):
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "success": False,
                "message": result.get("message", "Whisper transcription failed"),
                "audioPath": str(audio_path),
                "audio_path": str(audio_path),
                "model": result.get("model"),
            },
        )

    transcript = result.get("transcript", "")
    print(f"[Interview transcribe] transcript length={len(transcript)}")
    return {
        "status": "success",
        "success": True,
        "transcript": transcript,
        "audioPath": str(audio_path),
        "audio_path": str(audio_path),
        "model": result.get("model"),
    }


@router.post("/questions/{application_id}/evaluate")
def evaluate_interview_answer(application_id: str, request: AnswerEvaluationRequest):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if not _is_interview_access_verified(application):
        raise HTTPException(status_code=403, detail="Candidate verification is required before interview")

    question, question_index = _find_question_with_index(application, request.question_id)

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    transcript = str(request.transcript or "").strip()

    final_answer = transcript

    question_source = _get_question_source(application)
    evaluation = evaluate_answer_with_qwen(
        application,
        question,
        final_answer,
        question_index=question_index,
        question_source=question_source,
    )
    answer_record = _build_answer_record(
        request.question_id,
        question,
        final_answer,
        transcript,
        request.audio_path,
        evaluation,
    )
    print(
        "[Qwen grading] answerObjectBeforeSave="
        f"{json.dumps(answer_record, ensure_ascii=False)}"
    )

    interview_answers = application.get("interview_answers")

    if not isinstance(interview_answers, dict):
        interview_answers = {}

    interview_answers[request.question_id] = answer_record
    current_score = _average_answer_scores(interview_answers)
    save_success = update_application(
        application_id,
        {
            "interview_answers": interview_answers,
            "interview_status": "in_progress",
            "interview_completed": False,
            "interview_score": current_score,
        },
    )
    print(
        "[Qwen grading] "
        f"candidateId={application_id} questionId={request.question_id} "
        f"mongoSaveSuccess={save_success} gradingStatus={answer_record.get('gradingStatus')} "
        f"interviewScore={current_score}"
    )
    print(
        "[Qwen grading] answerObjectSaved="
        f"{json.dumps(answer_record, ensure_ascii=False)}"
    )

    if not save_success:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "success": False,
                "message": "Could not save answer grading. Please retry submission.",
                "reason": "MongoDB save failed",
            },
        )

    if evaluation.get("success") is not True:
        failure_message = (
            evaluation.get("message")
            if evaluation.get("reason") == "Qwen unavailable"
            else "Qwen grading failed. Please retry submission."
        )
        return JSONResponse(
            status_code=502,
            content={
                "status": "error",
                "success": False,
                "message": failure_message,
                "reason": evaluation.get("reason") or "Invalid JSON from Qwen",
                "gradingStatus": "grading_failed",
            },
        )

    return {
        "success": True,
        "status": "success",
        "message": "Answer submitted successfully.",
        "question_id": request.question_id,
        "submittedAt": answer_record["submittedAt"],
        "gradingStatus": "graded",
    }


@router.post("/questions/{application_id}/complete")
def complete_interview(application_id: str):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    question_payload = application.get("interview_questions") or {}
    questions = question_payload.get("questions") if isinstance(question_payload, dict) else []

    if not isinstance(questions, list):
        questions = []

    interview_answers = application.get("interview_answers")

    if not isinstance(interview_answers, dict):
        interview_answers = {}

    missing_or_ungraded = []

    for question in questions:
        if not isinstance(question, dict):
            continue

        question_id = str(question.get("id") or "")
        answer = interview_answers.get(question_id)

        if not question_id or not isinstance(answer, dict) or _get_grading_status(answer) != "graded":
            missing_or_ungraded.append(question_id or "unknown")

    if missing_or_ungraded:
        raise HTTPException(
            status_code=400,
            detail="All answers must be graded by Qwen before completing the interview.",
        )

    scores = [
        _extract_score(answer)
        for answer in interview_answers.values()
        if isinstance(answer, dict) and _get_grading_status(answer) == "graded"
    ]
    average_score = round(sum(scores) / len(scores), 1) if scores else 0
    updates = {
        "interview_answers": interview_answers,
        "interview_status": "completed",
        "interviewStatus": "completed",
        "interview_completed": True,
        "interviewCompleted": True,
        "interview_score": average_score,
        "interview_completed_at": datetime.now().isoformat(),
        "completedAt": datetime.now().isoformat(),
    }

    token = application.get("interview_token")

    if token:
        _mark_link_used(token)

    update_application(application_id, updates)

    return {
        "success": True,
        "interview_status": "completed",
        "interview_score": average_score,
        "answered_count": len([score for score in scores if score > 0]),
        "total_questions": len(questions),
    }


def _find_reference_face_path(application: dict):
    aadhaar_candidates = [
        application.get("aadhaar_face_image_path"),
        application.get("aadhaar_photo_path"),
        _safe_get(application, ["kyc_verification", "aadhaar_face_image_path"]),
        _safe_get(application, ["aadhaar_verification", "aadhaar_face_image_path"]),
        _safe_get(application, ["kyc", "aadhaar_photo_path"]),
        _safe_get(application, ["kyc", "photo_path"]),
        _safe_get(application, ["aadhaar", "photo_path"]),
        _safe_get(application, ["kyc_verification", "aadhaar_photo_path"]),
        _safe_get(application, ["aadhaar_verification", "aadhaar_photo_path"]),
    ]

    resume_candidates = [
        application.get("resume_face_image_path"),
        application.get("resume_photo_path"),
        _safe_get(application, ["resume", "resume_face_image_path"]),
        _safe_get(application, ["resume", "resume_photo_path"]),
        _safe_get(application, ["resume", "photo_path"]),
        _safe_get(application, ["resume", "face_path"]),
    ]

    candidate_image_candidates = [
        application.get("candidate_image_path"),
        application.get("profile_image_path"),
        _safe_get(application, ["candidate", "image_path"]),
        _safe_get(application, ["candidate", "face_image_path"]),
        _safe_get(application, ["profile", "image_path"]),
    ]

    checked_paths = []

    for candidate in aadhaar_candidates:
        resolved_path = _existing_path(candidate, checked_paths, "aadhaar_face")

        if resolved_path:
            print("[Interview face-verify] selected_reference_source=aadhaar_face")
            return resolved_path, "aadhaar_face", checked_paths

    for candidate in resume_candidates:
        resolved_path = _existing_path(candidate, checked_paths, "resume_face")

        if resolved_path:
            print("[Interview face-verify] selected_reference_source=resume_face")
            return resolved_path, "resume_face", checked_paths

    for candidate in candidate_image_candidates:
        resolved_path = _existing_path(candidate, checked_paths, "candidate_image")

        if resolved_path:
            print("[Interview face-verify] selected_reference_source=candidate_image")
            return resolved_path, "candidate_image", checked_paths

    print("[Interview face-verify] selected_reference_source=none")
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
    question, _ = _find_question_with_index(application, question_id)
    return question


def _find_question_with_index(application: dict, question_id: str) -> tuple[dict | None, int | None]:
    question_payload = application.get("interview_questions") or {}
    questions = question_payload.get("questions") if isinstance(question_payload, dict) else []

    if not isinstance(questions, list):
        return None, None

    for index, question in enumerate(questions):
        if isinstance(question, dict) and str(question.get("id")) == str(question_id):
            return question, index

    return None, None


def _get_question_source(application: dict) -> str:
    question_payload = application.get("interview_questions")

    if isinstance(question_payload, dict):
        return str(question_payload.get("question_source") or question_payload.get("source") or "")

    return str(application.get("question_source") or application.get("questionSource") or "")


def _prepare_interview_questions(application_id: str, application: dict) -> dict:
    existing_questions = application.get("interview_questions")
    job_id = str(application.get("job_id") or "")
    bank_questions = _normalize_interview_question_bank(load_question_bank(job_id))
    bank_exists = bool(bank_questions)

    if (
        isinstance(existing_questions, dict)
        and _has_current_question_contract(existing_questions)
        and (not bank_exists or existing_questions.get("source") == "question_bank")
    ):
        _log_question_load(application, existing_questions)
        return existing_questions

    if not bank_exists:
        result = {
            "success": True,
            "status": "empty",
            "source": "none",
            "question_source": "none",
            "candidate_name": _get_candidate_name(application),
            "questions": [],
            "message": "No question bank found",
        }
        _log_question_load(application, result)
        return result

    result = {
        "success": True,
        "status": "success",
        "source": "question_bank",
        "question_source": "question_bank",
        "candidate_name": _get_candidate_name(application),
        "question_bank_id": job_id,
        "question_bank_name": str(application.get("job_role") or application.get("job_title") or "Question Bank"),
        "questions": bank_questions,
    }

    update_application(
        application_id,
        {
            "interview_questions": result,
            "interviewQuestions": result.get("questions", []),
            "question_source": result.get("question_source") or result.get("source"),
            "questionSource": result.get("question_source") or result.get("source"),
            "question_bank_id": result.get("question_bank_id", application.get("question_bank_id")),
            "questionBankId": result.get("question_bank_id", application.get("question_bank_id")),
            "question_bank_name": result.get("question_bank_name", application.get("question_bank_name")),
            "questionBankName": result.get("question_bank_name", application.get("question_bank_name")),
        },
    )
    _log_question_load(application, result)
    return result


def _normalize_interview_question_bank(raw_questions) -> list[dict]:
    if not isinstance(raw_questions, list):
        return []

    normalized = []

    for index, item in enumerate(raw_questions, start=1):
        if not isinstance(item, dict):
            continue

        question_text = str(
            item.get("question")
            or item.get("questionText")
            or item.get("text")
            or ""
        ).strip()

        if not question_text:
            continue

        normalized.append(
            {
                "id": str(item.get("id") or item.get("question_id") or f"q{len(normalized) + 1}"),
                "question": question_text,
                "expectedAnswer": str(
                    item.get("expectedAnswer")
                    or item.get("expected_answer")
                    or item.get("answer")
                    or ""
                ).strip(),
                "expected_answer": str(
                    item.get("expected_answer")
                    or item.get("expectedAnswer")
                    or item.get("answer")
                    or ""
                ).strip(),
                "difficulty": str(item.get("difficulty") or "Medium").strip() or "Medium",
                "skill": str(
                    item.get("skill")
                    or item.get("category")
                    or item.get("topic")
                    or ""
                ).strip(),
                "category": str(
                    item.get("category")
                    or item.get("skill")
                    or item.get("topic")
                    or "Question Bank"
                ).strip(),
            }
        )

    return normalized


def _log_question_load(application: dict, question_payload: dict) -> None:
    questions = question_payload.get("questions") if isinstance(question_payload, dict) else []
    source = question_payload.get("question_source") or question_payload.get("source") or ""
    question_bank_found = source == "question_bank"
    print(
        "[Interview questions] "
        f"candidateId={application.get('application_id')} "
        f"jobId={application.get('job_id')} "
        f"questionBankFound={question_bank_found} "
        f"questionSource={source or 'unknown'} "
        f"questionsLoaded={len(questions) if isinstance(questions, list) else 0}"
    )


def _extract_score(evaluation) -> float:
    if not isinstance(evaluation, dict):
        return 0

    for key in ("finalScore", "final_score", "score", "overallScore", "overall_score", "totalScore", "total_score"):
        if key in evaluation:
            return float(normalize_score(evaluation.get(key)))

    grading = evaluation.get("grading")

    if isinstance(grading, dict):
        return _extract_score(grading)

    return 0


def _build_answer_record(
    question_id: str,
    question: dict,
    answer_text: str,
    transcript: str,
    audio_path: str,
    evaluation: dict,
) -> dict:
    grading_status = "graded" if evaluation.get("success") is True else "grading_failed"
    score = _extract_score(evaluation) if grading_status == "graded" else None
    submitted_at = datetime.now().isoformat()
    record = {
        "questionId": question_id,
        "question_id": question_id,
        "question": question.get("question", ""),
        "expectedAnswer": question.get("expected_answer") or question.get("expectedAnswer") or "",
        "expected_answer": question.get("expected_answer") or question.get("expectedAnswer") or "",
        "difficulty": question.get("difficulty") or "",
        "skill": question.get("skill") or question.get("category") or "",
        "category": question.get("category") or question.get("skill") or "",
        "answerText": answer_text,
        "answer_text": answer_text,
        "transcript": transcript,
        "audioPath": audio_path or "",
        "audio_path": audio_path or "",
        "evaluation": (
            evaluation
            if grading_status == "graded"
            else {
                "success": False,
                "gradingStatus": "grading_failed",
                "reason": evaluation.get("reason") or "Invalid JSON from Qwen",
            }
        ),
        "gradingStatus": grading_status,
        "grading_status": grading_status,
        "gradingModel": evaluation.get("gradingModel") or evaluation.get("model") or "",
        "grading_model": evaluation.get("gradingModel") or evaluation.get("model") or "",
        "submittedAt": submitted_at,
        "submitted_at": submitted_at,
    }

    if grading_status != "graded":
        record["gradingError"] = "Qwen grading failed. Please retry answer evaluation."
        record["gradingReason"] = evaluation.get("reason") or "Invalid JSON from Qwen"
        return record

    grading = {
        "finalScore": score,
        "relevance": normalize_score(evaluation.get("relevance")),
        "technical": normalize_score(evaluation.get("technical")),
        "depth": normalize_score(evaluation.get("depth")),
        "clarity": normalize_score(evaluation.get("clarity")),
        "feedback": evaluation.get("feedback") or "",
        "missingPoints": evaluation.get("missingPoints") or evaluation.get("missing_points") or [],
    }
    record.update(
        {
            "score": score,
            "finalScore": score,
            "final_score": score,
            "relevance": grading["relevance"],
            "technical": grading["technical"],
            "depth": grading["depth"],
            "clarity": grading["clarity"],
            "feedback": grading["feedback"],
            "missingPoints": grading["missingPoints"],
            "missing_points": grading["missingPoints"],
            "grading": grading,
        }
    )
    return record


def _average_answer_scores(interview_answers: dict) -> float:
    scores = [
        _extract_score(answer)
        for answer in interview_answers.values()
        if isinstance(answer, dict) and _get_grading_status(answer) == "graded"
    ]

    return round(sum(scores) / len(scores), 1) if scores else 0


def _get_grading_status(answer: dict) -> str:
    return str(answer.get("gradingStatus") or answer.get("grading_status") or "").lower()


def _candidate_folder(application: dict, application_id: str) -> Path:
    folder = application.get("candidate_folder")

    if folder:
        return Path(str(folder))

    return CANDIDATE_STORAGE_DIR / application_id


def _safe_audio_extension(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()

    if suffix in {".webm", ".wav", ".mp3", ".m4a", ".ogg", ".mp4"}:
        return suffix

    return ".webm"


def _is_interview_completed(application: dict) -> bool:
    return (
        application.get("interview_completed") is True
        or str(application.get("interview_status") or "").lower() == "completed"
    )


def _is_verification_completed(application: dict) -> bool:
    return (
        application.get("verification_completed") is True
        or str(application.get("verification_status") or "").lower() == "verified"
    )


def _is_interview_access_verified(application: dict) -> bool:
    return _is_aadhaar_verified(application) and _is_face_verified(application)


def _is_aadhaar_verified(application: dict) -> bool:
    return (
        application.get("aadhaarVerified") is True
        or application.get("aadhaar_verified") is True
        or str(application.get("verificationStatus") or "").lower() in {"aadhaar_passed", "verified"}
        or str(application.get("verification_status") or "").lower() in {"aadhaar_passed", "verified"}
    )


def _is_face_verified(application: dict) -> bool:
    live_face = application.get("live_face_verification")

    return (
        application.get("faceVerified") is True
        or application.get("face_verified") is True
        or (isinstance(live_face, dict) and str(live_face.get("status") or "").lower() == "passed")
        or str(application.get("verificationStatus") or "").lower() == "verified"
        or str(application.get("verification_status") or "").lower() == "verified"
    )


def _normalize_expiry_date(value: str | None) -> str:
    if value:
        parsed = datetime.fromisoformat(value)

        if len(value) <= 10:
            parsed = parsed.replace(hour=23, minute=59, second=59)

        return parsed.isoformat()

    return (datetime.now() + timedelta(days=7)).isoformat()


def _load_link_data(token: str) -> dict | None:
    file_path = INTERVIEW_LINK_DIR / f"{token}.json"

    if not file_path.exists():
        return None

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    return data if isinstance(data, dict) else None


def _mark_link_used(token: str) -> None:
    file_path = INTERVIEW_LINK_DIR / f"{token}.json"

    if not file_path.exists():
        return

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return

    data["used"] = True
    file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _has_current_question_contract(question_payload: dict) -> bool:
    questions = question_payload.get("questions")

    if not isinstance(questions, list) or not questions:
        return False

    if question_payload.get("source") == "question_bank":
        return all(isinstance(question, dict) and question.get("question") for question in questions)

    if len(questions) != 5:
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


def _get_candidate_name(application: dict) -> str:
    return (
        application.get("candidate_name")
        or _safe_get(application, ["resume", "candidate_name"])
        or application.get("resume_name")
        or application.get("file_name")
        or "Candidate"
    )
