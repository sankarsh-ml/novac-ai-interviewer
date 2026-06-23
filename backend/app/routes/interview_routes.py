import traceback
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.answer_evaluation_service import evaluate_answer_with_qwen
from app.services.db_service import get_resume_application, update_application
from app.services.json_storage_service import (
    delete_interview_session,
    get_interview_session,
    submitted_answer_count,
    update_interview_session,
    upsert_interview_session,
)
from app.services.whisper_service import preload_model, transcribe_and_save
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
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]

LIVE_FRAME_DIR = APP_DIR / "storage" / "live_frames"
LIVE_FRAME_DIR.mkdir(parents=True, exist_ok=True)

INTERVIEW_AUDIO_DIR = APP_DIR / "storage" / "interview_audio"
INTERVIEW_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

TEXT_DIR = APP_DIR / "storage" / "text"
TEXT_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_ANSWER_DIR = BACKEND_DIR / "uploads" / "audio_answers"
AUDIO_ANSWER_DIR.mkdir(parents=True, exist_ok=True)

TRANSCRIPT_DIR = BACKEND_DIR / "uploads" / "transcripts"
TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)

MAX_QUESTION_SCORE = 10


class AnswerEvaluationRequest(BaseModel):
    question_id: str
    answer_text: str


@router.post("/preload-whisper")
def preload_whisper():
    try:
        print("[Interview Whisper] Preload endpoint called", flush=True)
        preload_model()
        print("[Interview Whisper] Preload complete", flush=True)

        return {
            "success": True,
            "message": "Whisper model ready",
        }

    except Exception as error:
        print("[Interview Whisper] Preload failed", flush=True)
        print(traceback.format_exc(), flush=True)

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Whisper preload failed: {str(error)}",
            },
        )


@router.post("/face-verify/{application_id}")
async def face_verify(application_id: str, frame: UploadFile = File(...)):
    live_frame_path = None

    try:
        print(f"[Interview face-verify] application_id={application_id}", flush=True)
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
        print(f"[Interview face-verify] reference_source={reference_source}", flush=True)
        print(f"[Interview face-verify] reference_path={reference_path}", flush=True)
        print(
            "[Interview face-verify] reference_path_exists="
            f"{bool(reference_path and Path(reference_path).exists())}",
            flush=True,
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
        print(f"[Interview face-verify] saved_live_frame_path={live_frame_path}", flush=True)

        result = verify_faces(
            str(reference_path),
            str(live_frame_path),
            threshold=DEFAULT_FACE_VERIFY_THRESHOLD,
        )
        result["reference_source"] = reference_source

        if result.get("match"):
            _store_face_verified(application_id, application, result)

        print(f"[Interview face-verify] face_verification_result={result}", flush=True)

        return JSONResponse(status_code=200, content=result)

    except Exception as error:
        print("\n========== INTERVIEW FACE VERIFY CRASH ==========", flush=True)
        print(traceback.format_exc(), flush=True)
        print("=================================================\n", flush=True)

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
    audio: UploadFile = File(...),
):
    try:
        print("[Upload Audio] Step 1/5: Reading uploaded audio...", flush=True)
        audio_bytes = await audio.read()
        print(f"[Upload Audio] Step 2/5: Audio bytes received: {len(audio_bytes)}", flush=True)

        if not audio_bytes:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "Empty audio file",
                },
            )

        audio_path = INTERVIEW_AUDIO_DIR / f"{_safe_file_part(application_id)}.webm"
        audio_path.write_bytes(audio_bytes)

        print(f"[Upload Audio] Step 3/5: Audio saved to {audio_path}", flush=True)
        print(f"[Upload Audio] Audio file size: {audio_path.stat().st_size} bytes", flush=True)

        print("[Upload Audio] Step 4/5: Starting Whisper transcription...", flush=True)

        transcription_result = transcribe_and_save(
            audio_path=str(audio_path),
            session_id=_safe_file_part(application_id),
            question_id="upload_audio",
        )

        transcript = transcription_result.get("transcript", "")
        transcript_path = transcription_result.get("transcript_file_path", "")

        print("[Upload Audio] Step 5/5: Whisper transcription complete", flush=True)
        print(f"[Upload Audio] Transcript length: {len(transcript)} characters", flush=True)
        print(f"[Upload Audio] Transcript preview: {transcript[:150]}", flush=True)
        print(f"[Upload Audio] Transcript saved: {transcript_path}", flush=True)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Audio saved and transcribed",
                "transcript": transcript,
                "transcript_file_path": transcript_path,
            },
        )

    except Exception as error:
        print("[Upload Audio] CRASH", flush=True)
        print(traceback.format_exc(), flush=True)

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": str(error),
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
        session = _ensure_interview_session(application_id, application, existing_questions)
        return {**existing_questions, "session_id": session.get("session_id")}

    result = generate_interview_questions(application)
    session = _ensure_interview_session(application_id, application, result)
    return {**result, "session_id": session.get("session_id")}


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


@router.post("/{session_id}/question/{question_id}/audio-answer")
async def submit_audio_answer(
    session_id: str,
    question_id: str,
    audio: UploadFile = File(...),
):
    print("\n========== AUDIO ANSWER START ==========", flush=True)
    print(f"[Interview Audio] session_id={session_id}", flush=True)
    print(f"[Interview Audio] question_id={question_id}", flush=True)

    application = get_resume_application(session_id)

    if not application:
        print("[Interview Audio] ERROR: Interview session not found", flush=True)
        raise HTTPException(status_code=404, detail="Interview session not found")

    print("[Interview Audio] Step 1/8: Application loaded", flush=True)

    question_payload = _get_or_create_question_payload(session_id, application)
    question = _find_question({"interview_questions": question_payload}, question_id)

    if not question:
        print("[Interview Audio] ERROR: Question not found", flush=True)
        raise HTTPException(status_code=404, detail="Question not found")

    print("[Interview Audio] Step 2/8: Question found", flush=True)
    print(f"[Interview Audio] Question: {question.get('question', '')}", flush=True)

    print("[Interview Audio] Step 3/8: Reading uploaded audio...", flush=True)
    audio_bytes = await audio.read()
    print(f"[Interview Audio] Audio bytes received: {len(audio_bytes)}", flush=True)

    if not audio_bytes:
        print("[Interview Audio] ERROR: Empty audio file", flush=True)
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Empty audio file"},
        )

    safe_session_id = _safe_file_part(session_id)
    safe_question_id = _safe_file_part(question_id)
    submitted_at = _now()
    audio_extension = _get_audio_extension(audio.filename)

    audio_path = AUDIO_ANSWER_DIR / f"{safe_session_id}_{safe_question_id}_{uuid.uuid4().hex}{audio_extension}"

    print("[Interview Audio] Step 4/8: Saving audio file...", flush=True)
    audio_path.write_bytes(audio_bytes)
    print(f"[Interview Audio] Audio saved to: {audio_path}", flush=True)
    print(f"[Interview Audio] Audio file size: {audio_path.stat().st_size} bytes", flush=True)

    try:
        print("[Interview Audio] Step 5/8: Starting Whisper transcription...", flush=True)

        transcription_result = transcribe_and_save(
            audio_path=str(audio_path),
            session_id=safe_session_id,
            question_id=safe_question_id,
        )

        transcript = transcription_result.get("transcript", "")
        transcript_path = transcription_result.get("transcript_file_path", "")

        print("[Interview Audio] Whisper transcription complete", flush=True)
        print(f"[Interview Audio] Transcript length: {len(transcript)} characters", flush=True)
        print(f"[Interview Audio] Transcript preview: {transcript[:200]}", flush=True)
        print(f"[Interview Audio] Transcript path: {transcript_path}", flush=True)

    except Exception as error:
        print("[Interview Audio] CRASH during Whisper transcription", flush=True)
        print(traceback.format_exc(), flush=True)
        print("========== AUDIO ANSWER FAILED ==========\n", flush=True)

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Audio transcription failed: {str(error)}",
            },
        )

    try:
        print("[Interview Audio] Step 6/8: Starting answer evaluation...", flush=True)

        evaluation = evaluate_answer_with_qwen(application, question, transcript)

        print("[Interview Audio] Answer evaluation complete", flush=True)
        print(f"[Interview Audio] Evaluation: {evaluation}", flush=True)

    except Exception as error:
        print("[Interview Audio] CRASH during answer evaluation", flush=True)
        print(traceback.format_exc(), flush=True)
        print("========== AUDIO ANSWER FAILED ==========\n", flush=True)

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Answer evaluation failed: {str(error)}",
            },
        )

    answer_record = {
        "session_id": session_id,
        "candidate_id": session_id,
        "question_id": question_id,
        "question_text": question.get("question", ""),
        "difficulty": question.get("difficulty", ""),
        "audio_file_path": str(audio_path),
        "transcript_file_path": str(transcript_path),
        "transcript": transcript,
        "score": evaluation.get("score", 0),
        "feedback": evaluation.get("feedback") or evaluation.get("message") or "",
        "evaluation": evaluation,
        "submitted_at": submitted_at,
    }

    try:
        print("[Interview Audio] Step 7/8: Storing answer in local JSON...", flush=True)

        _store_audio_answer(session_id, application, question_payload, question, answer_record)

        print("[Interview Audio] Answer stored successfully", flush=True)

    except Exception as error:
        print("[Interview Audio] CRASH during local JSON storage", flush=True)
        print(traceback.format_exc(), flush=True)
        print("========== AUDIO ANSWER FAILED ==========\n", flush=True)

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Answer storage failed: {str(error)}",
            },
        )

    print("[Interview Audio] Step 8/8: Returning success response", flush=True)
    print("========== AUDIO ANSWER COMPLETE ==========\n", flush=True)

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Answer submitted successfully",
        },
    )


@router.post("/{session_id}/complete")
def complete_interview(session_id: str):
    application = get_resume_application(session_id)

    if not application:
        raise HTTPException(status_code=404, detail="Interview session not found")

    question_payload = _get_or_create_question_payload(session_id, application)
    session = get_interview_session(session_id) or _ensure_interview_session(
        session_id,
        application,
        question_payload,
    )

    questions = question_payload.get("questions") if isinstance(question_payload, dict) else []

    submitted_count = submitted_answer_count(session)
    submitted_answers = _submitted_session_questions(session)

    status = "completed" if submitted_count == 5 else "in_progress"
    completed_at = _now() if status == "completed" else session.get("completed_at")

    session.update(
        {
            "session_id": session_id,
            "candidate_id": session_id,
            "candidate_info": _candidate_info(application),
            "status": status,
            "total_score": _total_score(submitted_answers),
            "max_score": len(questions) * MAX_QUESTION_SCORE,
            "questions": session.get("questions", []),
            "submitted_answer_count": submitted_count,
            "completed_at": completed_at,
        }
    )

    upsert_interview_session(session)

    update_application(
        session_id,
        {
            "interview_session": session,
            "interview_status": status,
        },
    )

    return {
        "success": True,
        "status": status,
    }


@router.delete("/{session_id}/cleanup")
def cleanup_interview(session_id: str):
    session = get_interview_session(session_id)

    if not session:
        return {
            "success": True,
            "action": "not_found",
        }

    submitted_count = submitted_answer_count(session)

    if submitted_count == 0:
        _delete_session_files(session)
        delete_interview_session(session_id)
        update_application(session_id, {"interview_status": "abandoned", "interview_session": {}})
        return {
            "success": True,
            "action": "deleted",
        }

    if submitted_count < 5:
        session["status"] = "abandoned"
        session["abandoned_at"] = _now()
        upsert_interview_session(session)
        update_application(session_id, {"interview_status": "abandoned", "interview_session": session})
        return {
            "success": True,
            "action": "marked_abandoned",
        }

    submitted_answers = _submitted_session_questions(session)
    session["status"] = "completed"
    session["completed_at"] = session.get("completed_at") or _now()
    session["total_score"] = _total_score(submitted_answers)
    upsert_interview_session(session)
    update_application(session_id, {"interview_status": "completed", "interview_session": session})

    return {
        "success": True,
        "action": "completed",
    }


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


def _get_or_create_question_payload(application_id: str, application: dict) -> dict:
    question_payload = application.get("interview_questions")

    if isinstance(question_payload, dict) and _has_current_question_contract(question_payload):
        return question_payload

    question_payload = generate_interview_questions(application)
    _ensure_interview_session(application_id, application, question_payload)
    return question_payload


def _ensure_interview_session(application_id: str, application: dict, question_payload: dict) -> dict:
    questions = question_payload.get("questions") if isinstance(question_payload, dict) else []
    existing_session = get_interview_session(application_id) or application.get("interview_session")

    if not isinstance(existing_session, dict):
        existing_session = {}

    existing_answers = _answers_dict_to_list(application.get("interview_answers"))
    existing_questions = existing_session.get("questions") if isinstance(existing_session.get("questions"), list) else []
    submitted_answers = _submitted_session_questions(existing_session) or _submitted_answers(existing_answers)
    inferred_status = existing_session.get("status") or "in_progress"

    if len(submitted_answers) >= len(questions) and len(questions) == 5:
        inferred_status = "completed"

    session = {
        "session_id": application_id,
        "candidate_id": application_id,
        "candidate_name": _candidate_info(application).get("candidate_name"),
        "resume_file": application.get("file_name"),
        "status": inferred_status,
        "face_verified": bool(existing_session.get("face_verified")),
        "created_at": existing_session.get("created_at") or existing_session.get("started_at") or _now(),
        "completed_at": existing_session.get("completed_at"),
        "total_score": _total_score(submitted_answers),
        "max_score": len(questions) * MAX_QUESTION_SCORE,
        "questions": _session_questions_from_questions(questions, existing_questions, existing_answers),
        "candidate_info": _candidate_info(application),
    }

    session.update(
        {
            key: existing_session.get(key)
            for key in ("face_verified_at", "face_verification", "abandoned_at")
            if existing_session.get(key)
        }
    )

    session = upsert_interview_session(session)

    update_application(
        application_id,
        {
            "interview_questions": question_payload,
            "interview_session": session,
        },
    )

    return session


def _store_audio_answer(
    application_id: str,
    application: dict,
    question_payload: dict,
    question: dict,
    answer_record: dict,
) -> None:
    session = get_interview_session(application_id) or _ensure_interview_session(
        application_id,
        application,
        question_payload,
    )

    questions = question_payload.get("questions", [])
    session_questions = _session_questions_from_questions(questions, session.get("questions", []), [])
    updated_questions = []

    for session_question in session_questions:
        if str(session_question.get("question_id")) == str(question.get("id")):
            updated_questions.append(
                {
                    **session_question,
                    "audio_file_path": answer_record.get("audio_file_path"),
                    "transcript_file_path": answer_record.get("transcript_file_path"),
                    "transcript": answer_record.get("transcript"),
                    "score": answer_record.get("score"),
                    "feedback": answer_record.get("feedback"),
                    "evaluation": answer_record.get("evaluation"),
                    "submitted_at": answer_record.get("submitted_at"),
                }
            )
        else:
            updated_questions.append(session_question)

    submitted_answers = _submitted_session_questions({"questions": updated_questions})
    answered_count = len(submitted_answers)
    status = "completed" if len(questions) == 5 and answered_count >= len(questions) else "in_progress"

    if status == "completed":
        session["completed_at"] = _now()

    session.update(
        {
            "session_id": application_id,
            "candidate_id": application_id,
            "candidate_info": _candidate_info(application),
            "status": status,
            "total_score": _total_score(submitted_answers),
            "max_score": len(questions) * MAX_QUESTION_SCORE,
            "questions": updated_questions,
            "submitted_answer_count": answered_count,
        }
    )

    session = upsert_interview_session(session)

    interview_answers = {
        str(answer.get("question_id")): {
            "session_id": application_id,
            "candidate_id": application_id,
            "question_id": answer.get("question_id"),
            "question_text": answer.get("question_text"),
            "difficulty": answer.get("difficulty"),
            "audio_file_path": answer.get("audio_file_path"),
            "transcript_file_path": answer.get("transcript_file_path"),
            "transcript": answer.get("transcript"),
            "score": answer.get("score"),
            "feedback": answer.get("feedback"),
            "evaluation": answer.get("evaluation"),
            "submitted_at": answer.get("submitted_at"),
        }
        for answer in updated_questions
        if isinstance(answer, dict) and answer.get("submitted_at")
    }

    update_application(
        application_id,
        {
            "interview_session": session,
            "interview_answers": interview_answers,
            "interview_status": status,
        },
    )


def _store_face_verified(application_id: str, application: dict, result: dict) -> None:
    session = get_interview_session(application_id)

    if not isinstance(session, dict):
        question_payload = (
            application.get("interview_questions")
            if isinstance(application.get("interview_questions"), dict)
            else {"questions": []}
        )
        session = _ensure_interview_session(application_id, application, question_payload)

    session.update(
        {
            "session_id": application_id,
            "candidate_id": application_id,
            "candidate_info": _candidate_info(application),
            "status": session.get("status") or "in_progress",
            "face_verified": True,
            "face_verified_at": _now(),
            "face_verification": {
                "match": True,
                "score": result.get("score"),
                "threshold": result.get("threshold", DEFAULT_FACE_VERIFY_THRESHOLD),
                "reference_source": result.get("reference_source"),
            },
        }
    )

    session = upsert_interview_session(session)
    update_application(application_id, {"interview_session": session})


def _session_questions_from_questions(
    questions: list,
    existing_questions: list[dict] | None = None,
    answers: list[dict] | None = None,
) -> list[dict]:
    existing_by_question = {
        str(question.get("question_id")): question
        for question in existing_questions or []
        if isinstance(question, dict)
    }

    answers_by_question = {
        str(answer.get("question_id")): answer
        for answer in answers or []
        if isinstance(answer, dict)
    }

    session_questions = []

    for question in questions if isinstance(questions, list) else []:
        if not isinstance(question, dict):
            continue

        question_id = str(question.get("id"))
        existing = existing_by_question.get(question_id, {})
        answer = answers_by_question.get(question_id, {})

        session_questions.append(
            {
                "question_id": question_id,
                "question_text": question.get("question", ""),
                "category": question.get("category", ""),
                "difficulty": str(question.get("difficulty", "")).lower(),
                "audio_file_path": answer.get("audio_file_path", existing.get("audio_file_path")),
                "transcript_file_path": answer.get("transcript_file_path", existing.get("transcript_file_path")),
                "transcript": answer.get("transcript", existing.get("transcript")),
                "score": answer.get("score", existing.get("score")),
                "feedback": answer.get("feedback", existing.get("feedback")),
                "evaluation": answer.get("evaluation", existing.get("evaluation")),
                "submitted_at": answer.get("submitted_at", existing.get("submitted_at")),
            }
        )

    return session_questions


def _answers_dict_to_list(value) -> list[dict]:
    if isinstance(value, list):
        return [answer for answer in value if isinstance(answer, dict)]

    if not isinstance(value, dict):
        return []

    answers = []

    for question_id, answer in value.items():
        if not isinstance(answer, dict):
            continue

        evaluation = answer.get("evaluation") if isinstance(answer.get("evaluation"), dict) else {}

        answers.append(
            {
                "session_id": answer.get("session_id"),
                "candidate_id": answer.get("candidate_id"),
                "question_id": answer.get("question_id") or question_id,
                "question_text": answer.get("question_text"),
                "difficulty": answer.get("difficulty"),
                "audio_file_path": answer.get("audio_file_path"),
                "transcript_file_path": answer.get("transcript_file_path"),
                "transcript": answer.get("transcript") or answer.get("answer_text", ""),
                "score": answer.get("score", evaluation.get("score", 0)),
                "feedback": answer.get("feedback", evaluation.get("feedback", "")),
                "evaluation": evaluation,
                "submitted_at": answer.get("submitted_at"),
            }
        )

    return answers


def _submitted_answers(answers: list[dict]) -> list[dict]:
    return [
        answer
        for answer in answers
        if isinstance(answer, dict)
        and (
            answer.get("submitted_at")
            or answer.get("transcript")
            or answer.get("evaluation")
        )
    ]


def _submitted_session_questions(session: dict) -> list[dict]:
    questions = session.get("questions") if isinstance(session, dict) else []

    if not isinstance(questions, list):
        return []

    return [
        question
        for question in questions
        if isinstance(question, dict)
        and (
            question.get("submitted_at")
            or question.get("transcript")
            or question.get("score") is not None
        )
    ]


def _delete_session_files(session: dict) -> None:
    questions = session.get("questions") if isinstance(session, dict) else []

    if not isinstance(questions, list):
        return

    for question in questions:
        if not isinstance(question, dict):
            continue

        for key in ("audio_file_path", "transcript_file_path"):
            file_path = question.get(key)

            if not file_path:
                continue

            try:
                Path(str(file_path)).unlink(missing_ok=True)
            except OSError:
                pass


def _candidate_info(application: dict) -> dict:
    return {
        "application_id": application.get("application_id"),
        "candidate_name": (
            application.get("candidate_name")
            or _safe_get(application, ["resume", "candidate_name"])
            or application.get("file_name")
            or "Candidate"
        ),
        "file_name": application.get("file_name"),
        "job_id": application.get("job_id"),
        "email": application.get("email") or _safe_get(application, ["resume", "email"]),
        "phone": application.get("phone") or _safe_get(application, ["resume", "phone"]),
    }


def _total_score(answers: list[dict]) -> int | float:
    total = 0.0

    for answer in answers:
        try:
            total += float(answer.get("score", 0))
        except (TypeError, ValueError):
            continue

    return int(total) if total.is_integer() else round(total, 1)


def _safe_file_part(value: str) -> str:
    safe = "".join(
        character if character.isalnum() or character in ("-", "_") else "_"
        for character in str(value)
    )
    return safe[:80] or "answer"


def _get_audio_extension(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    return suffix if suffix in {".webm", ".wav", ".mp3", ".m4a", ".ogg"} else ".webm"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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