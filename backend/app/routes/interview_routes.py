import traceback
import sys
import uuid
import json
import os
import base64
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.application.services.answer_evaluation_service import evaluate_answer_with_qwen, normalize_score
from app.application.services.application_store_service import get_resume_application, update_application
from app.application.services.face_verification_service import (
    DEFAULT_FACE_VERIFY_THRESHOLD,
    analyze_face_image_bytes,
    cosine_similarity,
    get_dependency_status,
    get_face_app,
    materialize_file_from_mongo,
    verify_faces,
)
from app.application.services.identity_config_service import (
    GOVERNMENT_ID_SOURCE,
    RESUME_PHOTO_REQUIRED_MESSAGE,
    RESUME_PHOTO_SOURCE,
    build_identity_config,
    normalize_requested_identity_config,
    requires_government_id,
)
from app.application.services.question_generation_service import generate_interview_questions, generate_qwen_interview_questions
from app.application.services.question_bank_service import load_question_bank
from app.application.services.qwen_service import is_qwen_available
from app.application.services.whisper_service import transcribe_audio
from app.application.services.interview_service import (
    get_interview_by_id,
    get_link_by_token,
    mark_link_used,
    upsert_interview_for_candidate,
)
from app.core.config import get_path
from app.infrastructure.database.mongo_service import get_database
from app.repositories.job_repository import get_by_id as get_job_by_id
from app.utils.interview_tokens import generate_interview_token, get_interview_link_token


router = APIRouter()

PROJECT_ROOT = get_path("project_root")
APP_ROOT = get_path("backend_root") / "app"
LIVE_FRAME_DIR = get_path("live_frame_temp_dir")
LIVE_FRAME_DIR.mkdir(parents=True, exist_ok=True)
CANDIDATE_STORAGE_DIR = get_path("candidate_temp_dir")
JOIN_WINDOW_MINUTES = 60
HEARTBEAT_TIMEOUT_SECONDS = 120


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
    interview_date: str | None = None
    interview_time: str | None = None
    interview_scheduled_at: str | None = None


class LivenessEventRequest(BaseModel):
    type: str
    message: str = ""
    question_index: int | None = None
    timestamp: str | None = None


class LivenessImageRequest(BaseModel):
    image: str = ""
    images: list[str] = Field(default_factory=list)
    question_index: int | None = None
    question_id: str = ""
    check_type: str = ""


class AnswerSaveRequest(BaseModel):
    question_index: int
    question_id: str = ""
    question: str = ""
    expected_answer: str = ""
    candidate_answer: str = ""
    score: float | None = None
    feedback: str | None = None
    status: str = "submitted"
    submitted_at: str | None = None


class QuestionFilters(BaseModel):
    difficulty: str = "all"
    area_of_interest: str = "all"
    search: str = ""
    tags: list[str] = Field(default_factory=list)
    job_role: str = "all"


class DifficultySplit(BaseModel):
    easy: Any = 0
    medium: Any = 0
    hard: Any = 0


class IdentityConfigRequest(BaseModel):
    requireGovernmentId: bool | None = None
    require_government_id: bool | None = None
    faceVerificationSource: str = ""
    face_verification_source: str = ""


class ConfigureQuestionsRequest(BaseModel):
    number_of_questions: Any = None
    questionCount: Any = None
    selected_question_ids: list[str] = Field(default_factory=list)
    selectedQuestionIds: list[str] = Field(default_factory=list)
    filters_used: QuestionFilters = Field(default_factory=QuestionFilters)
    question_source: str = "question_bank"
    questionSource: str = ""
    difficulty_split: DifficultySplit | dict | None = None
    difficultySplit: DifficultySplit | dict | None = None
    identity_config: IdentityConfigRequest | dict | None = None
    identityConfig: IdentityConfigRequest | dict | None = None
    identity_verification_required: bool | None = None
    identityVerificationRequired: bool | None = None


class RescheduleInterviewRequest(ConfigureQuestionsRequest):
    application_id: str = ""
    candidateId: str = ""
    candidate_id: str = ""
    jobId: str = ""
    job_id: str = ""
    interviewId: str = ""
    interview_id: str = ""
    candidate_name: str = ""
    email: str = ""
    expiry_date: str | None = None
    interview_date: str | None = None
    interview_time: str | None = None
    interview_scheduled_at: str | None = None
    scheduledAt: str | None = None
    scheduled_at: str | None = None
    durationMinutes: Any = None
    duration_minutes: Any = None


@router.post("/create-link")
def create_interview_link(payload: CreateInterviewLinkRequest):
    application = get_resume_application(payload.application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if _is_interview_completed(application):
        raise HTTPException(status_code=400, detail="Interview already completed")

    existing_link = application.get("interview_link") or application.get("verification_link")

    if existing_link:
        update_application(
            payload.application_id,
            {
                "interview_link": existing_link,
                "verification_link": existing_link,
                "interview_link_generated": True,
                "interview_link_generated_at": application.get("interview_link_generated_at") or datetime.now().isoformat(),
            },
        )
        return _existing_interview_link_response(application, existing_link)

    current_status = _normalize_interview_status(application)

    if current_status in {"partial"}:
        raise HTTPException(status_code=400, detail="This candidate already has an interview attempt recorded.")

    schedule = _normalize_schedule(payload, application)

    if not schedule:
        raise HTTPException(status_code=400, detail="Set a proper interview date and time.")

    if _join_window_end(schedule["scheduled_at"]) < _now_minute():
        raise HTTPException(
            status_code=400,
            detail="Set a proper interview date and time. This interview schedule is already expired.",
        )

    configured_questions = _get_configured_question_payload(application)

    if not configured_questions:
        raise HTTPException(
            status_code=400,
            detail="No interview questions configured. Please select questions before generating the link.",
        )

    interview_config = application.get("interview_config") if isinstance(application.get("interview_config"), dict) else {}
    selected_ids = interview_config.get("selected_question_ids") if isinstance(interview_config.get("selected_question_ids"), list) else []
    requested_count = int(interview_config.get("number_of_questions") or application.get("total_questions") or 0)
    configured_count = len(configured_questions.get("questions") or [])
    question_source = str(interview_config.get("question_source") or configured_questions.get("question_source") or configured_questions.get("source") or "question_bank")
    identity_config = build_identity_config(application)

    if requested_count <= 0 or configured_count != requested_count:
        raise HTTPException(
            status_code=400,
            detail="Configured question count must exactly match number_of_questions before generating the link.",
        )

    if question_source == "question_bank" and len(selected_ids) != requested_count:
        raise HTTPException(
            status_code=400,
            detail="Selected question count must exactly match number_of_questions before generating the link.",
        )

    token = generate_interview_token()
    attempt_number = _next_attempt_number(application)
    expiry_date = _normalize_expiry_date(payload.expiry_date)
    frontend_base_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
    verification_url = f"{frontend_base_url}/verify/{payload.application_id}?attempt={token}"
    interview_url = f"{frontend_base_url}/interview/{payload.application_id}?attempt={token}"
    data = {
        "application_id": payload.application_id,
        "candidate_name": payload.candidate_name or _get_candidate_name(application),
        "email": payload.email or application.get("email", ""),
        "expiry_date": expiry_date,
        "interview_date": schedule["date"],
        "interview_time": schedule["time"],
        "interview_scheduled_at": schedule["scheduled_at"].isoformat(),
        "used": False,
        "link": verification_url,
        "verification_url": verification_url,
        "interview_url": interview_url,
        "questionSource": question_source,
        "question_source": question_source,
        "difficultySplit": interview_config.get("difficulty_split") or {},
        "difficulty_split": interview_config.get("difficulty_split") or {},
        "selectedQuestionIds": selected_ids,
        "selected_question_ids": selected_ids,
        "finalQuestions": configured_questions.get("questions") or [],
        "final_questions": configured_questions.get("questions") or [],
        "identityConfig": identity_config,
        "identity_config": identity_config,
    }

    upsert_interview_for_candidate(
        payload.application_id,
        {
            **data,
            "interviewId": data.get("interviewId") or token,
            "jobId": application.get("jobId") or application.get("job_id"),
            "job_id": application.get("job_id") or application.get("jobId"),
            "interviewLinkToken": token,
            "status": "configured",
            "attempt_number": attempt_number,
        },
        {"createdAt": datetime.now().isoformat()},
    )
    print(
        "[InterviewCreate] "
        f"candidateId={payload.application_id} jobId={application.get('jobId') or application.get('job_id')} "
        f"interviewId={token} interviewLinkToken={token} status=configured"
    )
    update_application(
        payload.application_id,
        {
            "interview_link": verification_url,
            "verification_link": verification_url,
            "interview_token": token,
            "expiry_date": expiry_date,
            "interview_date": schedule["date"],
            "interview_time": schedule["time"],
            "interview_scheduled_at": schedule["scheduled_at"].isoformat(),
            "interview_link_generated": True,
            "interview_link_generated_at": datetime.now().isoformat(),
            "interview_status": "not_started",
            "interviewStatus": "not_started",
            "interview_completed": False,
            "interviewCompleted": False,
            "active_attempt_id": token,
            "attempt_number": attempt_number,
            "questionSource": question_source,
            "question_source": question_source,
            "finalQuestions": configured_questions.get("questions") or [],
            "final_questions": configured_questions.get("questions") or [],
            "identityConfig": identity_config,
            "identity_config": identity_config,
        },
    )

    return {
        "success": True,
        "link": verification_url,
        "interviewLink": verification_url,
        "interviewLinkToken": token,
        "verificationUrl": verification_url,
        "verification_url": verification_url,
        "interviewUrl": interview_url,
        "interview_url": interview_url,
        "expiry_date": expiry_date,
        "interview_date": schedule["date"],
        "interview_time": schedule["time"],
        "interview_scheduled_at": schedule["scheduled_at"].isoformat(),
        "interview_link_generated": True,
        "already_generated": False,
        "interview_status": "not_started",
        "attempt_number": attempt_number,
        "active_attempt_id": token,
        "identityConfig": identity_config,
        "identity_config": identity_config,
    }


@router.post("/reschedule-link")
def reschedule_interview_link(payload: RescheduleInterviewRequest):
    return _reschedule_interview_attempt(payload, payload.interviewId or payload.interview_id)


@router.post("/{interview_id}/reschedule")
def reschedule_interview_by_id(interview_id: str, payload: RescheduleInterviewRequest):
    return _reschedule_interview_attempt(payload, interview_id)


def _reschedule_interview_attempt(payload: RescheduleInterviewRequest, interview_id: str | None = None):
    application_id = str(payload.application_id or payload.candidateId or payload.candidate_id or "").strip()
    old_interview = get_interview_by_id(str(interview_id or "").strip())

    if not application_id and old_interview:
        application_id = str(old_interview.get("application_id") or old_interview.get("candidateId") or "").strip()

    if not application_id:
        raise HTTPException(status_code=400, detail="Cannot reschedule because candidate or job information is missing.")

    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Interview not found.")

    old_interview_id = str(
        interview_id
        or payload.interviewId
        or payload.interview_id
        or application.get("active_attempt_id")
        or get_interview_link_token(application)
        or application.get("interviewId")
        or ""
    ).strip()

    if not old_interview:
        old_interview = get_interview_by_id(old_interview_id)

    if not old_interview:
        raise HTTPException(status_code=404, detail="Interview not found.")

    if not (application.get("job_id") or application.get("jobId") or payload.job_id or payload.jobId):
        raise HTTPException(status_code=400, detail="Cannot reschedule because candidate or job information is missing.")

    if _is_interview_completed(application) or _is_interview_completed({**application, **old_interview}):
        raise HTTPException(status_code=400, detail="Completed interviews cannot be rescheduled.")

    if not _has_scheduled_interview({**application, **old_interview}):
        raise HTTPException(status_code=400, detail="Interview has not been scheduled yet.")

    can_reschedule, rejection_message = _can_reschedule_interview(application)

    if not can_reschedule:
        raise HTTPException(status_code=400, detail=rejection_message)

    if payload.scheduledAt and not payload.interview_scheduled_at:
        payload.interview_scheduled_at = payload.scheduledAt

    if payload.scheduled_at and not payload.interview_scheduled_at:
        payload.interview_scheduled_at = payload.scheduled_at

    schedule = _normalize_schedule(payload, application)

    if not schedule:
        raise HTTPException(status_code=400, detail="Set a proper interview date and time.")

    if _join_window_end(schedule["scheduled_at"]) < _now_minute():
        raise HTTPException(
            status_code=400,
            detail="Set a proper interview date and time. This interview schedule is already expired.",
        )

    configuration = _build_interview_configuration(application_id, application, payload)
    question_source = configuration["question_source"]
    selected_ids = configuration["selected_ids"]
    interview_config = configuration["interview_config"]
    interview_payload = configuration["interview_payload"]
    final_questions = configuration["questions"]
    identity_config = configuration["identity_config"]
    requested_count = configuration["requested_count"]
    split = configuration["difficulty_split"]
    duration_minutes = _parse_positive_question_count(payload.durationMinutes or payload.duration_minutes)
    existing_interview_id = str(old_interview.get("interviewId") or old_interview.get("interview_id") or old_interview_id or "").strip()
    existing_token = get_interview_link_token(old_interview) or get_interview_link_token(application)

    if not existing_interview_id or not existing_token:
        raise HTTPException(status_code=400, detail="Existing interview link is missing. Generate the interview link before rescheduling.")

    current_attempt_number = _current_attempt_number({**application, **old_interview})
    next_attempt_number = current_attempt_number + 1
    expiry_date = _normalize_expiry_date(payload.expiry_date)
    frontend_base_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
    verification_url = (
        application.get("interview_link")
        or application.get("verification_link")
        or old_interview.get("link")
        or old_interview.get("verification_url")
        or f"{frontend_base_url}/verify/{application_id}?attempt={existing_token}"
    )
    interview_url = (
        application.get("interview_url")
        or old_interview.get("interview_url")
        or f"{frontend_base_url}/interview/{application_id}?attempt={existing_token}"
    )
    now = datetime.now().isoformat()
    current_status = _normalize_interview_status(application)
    snapshot = _current_attempt_snapshot(application, current_status, now)

    if snapshot:
        snapshot = {
            **snapshot,
            "reschedule_status": "rescheduled",
            "rescheduled_at": now,
            "attempt_number": current_attempt_number,
            "attemptNumber": current_attempt_number,
        }
        archived_attempts = _upsert_attempt_snapshot(application.get("interview_attempts"), snapshot)
    else:
        archived_attempts = _archive_current_attempt(application, current_status)

    _archive_interview_answers(existing_interview_id, current_attempt_number, now)
    _archive_interview_answers(existing_token, current_attempt_number, now)

    print(
        "[Reschedule] "
        f"interviewId={existing_interview_id} token={existing_token} attemptNumber={next_attempt_number}"
    )

    update_application(
        application_id,
        {
            "interview_attempts": archived_attempts,
            "currentInterviewId": existing_interview_id,
            "current_interview_id": existing_interview_id,
            "interviewId": existing_interview_id,
            "interview_id": existing_interview_id,
            "interview_config": interview_config,
            "interview_questions": interview_payload,
            "interviewQuestions": final_questions,
            "generatedQuestions": interview_payload.get("generatedQuestions") or [],
            "generated_questions": interview_payload.get("generated_questions") or [],
            "finalQuestions": final_questions,
            "final_questions": final_questions,
            "question_source": question_source,
            "questionSource": question_source,
            "selectedQuestionIds": selected_ids,
            "selected_question_ids": selected_ids,
            "difficultySplit": split,
            "difficulty_split": split,
            "identityConfig": identity_config,
            "identity_config": identity_config,
            "total_questions": requested_count,
            "interview_link": verification_url,
            "verification_link": verification_url,
            "interview_url": interview_url,
            "interview_token": existing_token,
            "expiry_date": expiry_date,
            "interview_date": schedule["date"],
            "interview_time": schedule["time"],
            "interview_scheduled_at": schedule["scheduled_at"].isoformat(),
            "interview_link_generated": True,
            "interview_link_generated_at": now,
            "interview_status": "not_started",
            "interviewStatus": "not_started",
            "interview_completed": False,
            "interviewCompleted": False,
            "interview_answers": {},
            "interview_score": 0,
            "average_interview_score": 0,
            "answered_count": 0,
            "unanswered_count": 0,
            "interview_started_at": None,
            "interview_completed_at": None,
            "completedAt": None,
            "interview_quit_at": None,
            "interview_last_seen_at": None,
            "interview_session_id": "",
            "active_attempt_id": existing_token,
            "attempt_number": next_attempt_number,
            "attemptNumber": next_attempt_number,
            "rescheduled_at": now,
            "rescheduledAt": now,
        },
    )
    _reset_rescheduled_candidate_fields(application_id)
    _update_rescheduled_interview_record(
        existing_interview_id,
        existing_token,
        {
            "interviewId": existing_interview_id,
            "interview_id": existing_interview_id,
            "candidateId": application_id,
            "application_id": application_id,
            "candidate_name": payload.candidate_name or _get_candidate_name(application),
            "email": payload.email or application.get("email", ""),
            "jobId": application.get("jobId") or application.get("job_id") or payload.jobId or payload.job_id,
            "job_id": application.get("job_id") or application.get("jobId") or payload.job_id or payload.jobId,
            "attemptNumber": next_attempt_number,
            "attempt_number": next_attempt_number,
            "expiry_date": expiry_date,
            "interview_date": schedule["date"],
            "interview_time": schedule["time"],
            "interview_scheduled_at": schedule["scheduled_at"].isoformat(),
            "scheduledAt": schedule["scheduled_at"].isoformat(),
            "scheduled_at": schedule["scheduled_at"].isoformat(),
            "durationMinutes": duration_minutes,
            "duration_minutes": duration_minutes,
            "used": False,
            "link": verification_url,
            "verification_url": verification_url,
            "interview_url": interview_url,
            "interviewLinkToken": existing_token,
            "status": "configured",
            "interviewStatus": "Not Started",
            "interview_status": "not_started",
            "questionSource": question_source,
            "question_source": question_source,
            "difficultySplit": split,
            "difficulty_split": split,
            "selectedQuestionIds": selected_ids,
            "selected_question_ids": selected_ids,
            "generatedQuestions": interview_payload.get("generatedQuestions") or [],
            "generated_questions": interview_payload.get("generated_questions") or [],
            "questionCount": requested_count,
            "question_count": requested_count,
            "finalQuestions": final_questions,
            "final_questions": final_questions,
            "identityConfig": identity_config,
            "identity_config": identity_config,
            "rescheduledAt": now,
            "rescheduled_at": now,
            "updatedAt": now,
        },
    )

    return {
        "success": True,
        "rescheduled": True,
        "link": verification_url,
        "interviewLink": verification_url,
        "interviewLinkToken": existing_token,
        "verificationUrl": verification_url,
        "verification_url": verification_url,
        "interviewUrl": interview_url,
        "interview_url": interview_url,
        "interviewId": existing_interview_id,
        "expiry_date": expiry_date,
        "interview_date": schedule["date"],
        "interview_time": schedule["time"],
        "interview_scheduled_at": schedule["scheduled_at"].isoformat(),
        "interview_link_generated": True,
        "already_generated": True,
        "interview_status": "not_started",
        "attempt_number": next_attempt_number,
        "active_attempt_id": existing_token,
        "identityConfig": identity_config,
        "identity_config": identity_config,
        "message": "Interview rescheduled successfully.",
    }


def _archive_interview_answers(interview_id: str, attempt_number: int, timestamp: str) -> None:
    if not interview_id:
        return

    get_database().interview_answers.update_many(
        {"interviewId": str(interview_id), "archived": {"$ne": True}},
        {
            "$set": {
                "archived": True,
                "archivedReason": "rescheduled",
                "archived_reason": "rescheduled",
                "archivedAt": timestamp,
                "archived_at": timestamp,
                "attemptNumber": attempt_number,
                "attempt_number": attempt_number,
                "updatedAt": timestamp,
            }
        },
    )


def _reset_rescheduled_candidate_fields(application_id: str) -> None:
    if not application_id:
        return

    get_database().candidates.update_one(
        {
            "$or": [
                {"application_id": str(application_id)},
                {"candidateId": str(application_id)},
                {"candidate_id": str(application_id)},
            ]
        },
        {
            "$unset": {
                "completedAt": "",
                "completed_at": "",
                "interview_completed_at": "",
                "startedAt": "",
                "started_at": "",
                "interview_started_at": "",
                "expiredAt": "",
                "expired_at": "",
                "expiresAt": "",
                "expires_at": "",
                "interview_quit_at": "",
                "interview_session_id": "",
            }
        },
    )


def _update_rescheduled_interview_record(interview_id: str, token: str, set_values: dict) -> None:
    unset_values = {
        "completedAt": "",
        "completed_at": "",
        "interview_completed_at": "",
        "startedAt": "",
        "started_at": "",
        "interview_started_at": "",
        "expiredAt": "",
        "expired_at": "",
        "expiresAt": "",
        "expires_at": "",
        "error": "",
        "expired": "",
        "expiredReason": "",
        "expired_reason": "",
    }

    for field in set_values:
        unset_values.pop(field, None)

    get_database().interviews.update_one(
        {
            "$or": [
                {"interviewId": str(interview_id)},
                {"interview_id": str(interview_id)},
                {"interviewLinkToken": str(token)},
                {"token": str(token)},
                {"linkToken": str(token)},
                {"interview_token": str(token)},
            ]
        },
        {
            "$set": set_values,
            "$unset": unset_values,
        },
    )


def _existing_interview_link_response(application: dict, existing_link: str) -> dict:
    identity_config = build_identity_config(application)
    return {
        "success": True,
        "link": existing_link,
        "interviewLink": existing_link,
        "interviewLinkToken": get_interview_link_token(application),
        "verificationUrl": existing_link,
        "verification_url": existing_link,
        "interviewUrl": application.get("interview_url") or existing_link.replace("/verify/", "/interview/"),
        "interview_url": application.get("interview_url") or existing_link.replace("/verify/", "/interview/"),
        "expiry_date": application.get("expiry_date") or "",
        "interview_date": application.get("interview_date") or "",
        "interview_time": application.get("interview_time") or "",
        "interview_scheduled_at": application.get("interview_scheduled_at") or "",
        "interview_link_generated": True,
        "already_generated": True,
        "identityConfig": identity_config,
        "identity_config": identity_config,
        "message": "Interview link has already been generated. Use Copy Link from the shortlisted candidates page.",
    }


@router.get("/validate-token/{token}")
def validate_token(token: str):
    print(f"[InterviewOpen] token={token}")
    link_data = _load_link_data(token)

    if not link_data:
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "Interview link not found."},
        )

    final_questions = link_data.get("finalQuestions") or link_data.get("final_questions") or []
    print(f"[InterviewOpen] matchedBy={link_data.get('_matchedBy') or 'unknown'}")
    print(f"[InterviewOpen] interviewId={link_data.get('interviewId') or link_data.get('interview_id') or ''}")
    print(f"[InterviewOpen] status={link_data.get('status') or link_data.get('interview_status') or ''}")
    print(f"[InterviewOpen] finalQuestionsCount={len(final_questions) if isinstance(final_questions, list) else 0}")

    application = get_resume_application(link_data.get("application_id"))

    if not application:
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "Candidate not found for this interview link."},
        )

    job_id = link_data.get("jobId") or link_data.get("job_id") or application.get("jobId") or application.get("job_id")

    if job_id and not get_job_by_id(str(job_id)):
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "Job not found for this interview link."},
        )

    if link_data.get("used") or _is_interview_completed(application):
        return JSONResponse(
            status_code=409,
            content={"success": False, "message": "Interview has already been completed."},
        )

    if not isinstance(final_questions, list) or not final_questions:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Interview has no configured questions."},
        )

    try:
        expiry_date = datetime.fromisoformat(str(link_data["expiry_date"]))
    except Exception:
        expiry_date = datetime.now() - timedelta(seconds=1)

    if datetime.now() > expiry_date:
        return JSONResponse(
            status_code=410,
            content={"success": False, "message": "Interview link expired."},
        )

    return {
        "success": True,
        "message": "Interview Link Valid",
        "application_id": link_data["application_id"],
        "interviewId": link_data.get("interviewId") or link_data.get("interview_id") or "",
        "interviewLinkToken": get_interview_link_token(link_data),
        "candidate_name": link_data.get("candidate_name") or _get_candidate_name(application),
        "email": link_data.get("email") or application.get("email", ""),
        "expiry_date": link_data["expiry_date"],
        "identityConfig": build_identity_config(application),
        "identity_config": build_identity_config(application),
    }


@router.get("/access/{application_id}")
def check_interview_access(application_id: str, attempt: str | None = None):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    attempt_error = _attempt_access_error(application, attempt)

    if attempt_error:
        return attempt_error

    return _build_access_response(application)


@router.get("/{application_id}/access-status")
def check_interview_access_status(application_id: str):
    return check_interview_access(application_id)


@router.get("/{application_id}/configure-data")
def get_interview_configure_data(application_id: str):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    job_id = str(application.get("job_id") or "")
    questions = load_question_bank(job_id)
    question_bank_count = len(questions)
    default_question_source = "question_bank" if question_bank_count > 0 else "qwen_generated"
    print(
        "[Interview configure-data] "
        f"candidateId={application_id} jobId={job_id} totalQuestionBankCount={question_bank_count} "
        f"defaultQuestionSource={default_question_source}"
    )
    if question_bank_count == 0:
        print("[Interview configure-data] auto-switched to Qwen because question bank is empty")
    identity_config = build_identity_config(application)
    areas = sorted({
        question.get("area_of_interest") or question.get("areaOfInterest") or question.get("category") or "General"
        for question in questions
    })
    job_roles = sorted({
        question.get("job_role") or question.get("jobRole")
        for question in questions
        if question.get("job_role") or question.get("jobRole")
    })
    tags = sorted({
        tag
        for question in questions
        for tag in (question.get("tags") if isinstance(question.get("tags"), list) else [])
    })

    return {
        "success": True,
        "application": {
            "application_id": application.get("application_id") or application_id,
            "candidate_name": _get_candidate_name(application),
            "email": application.get("email") or "",
            "job_id": job_id,
            "job_title": application.get("job_title") or application.get("job_role") or "",
            "interview_status": _normalize_interview_status(application),
            "interviewStatus": _normalize_interview_status(application),
            "interview_completed": _is_interview_completed(application),
            "report_available": select_report_application(application) is not None,
            "interview_date": application.get("interview_date") or "",
            "interview_time": application.get("interview_time") or "",
            "interview_scheduled_at": application.get("interview_scheduled_at") or "",
            "interview_link": application.get("interview_link") or application.get("verification_link") or "",
            "interview_link_generated": bool(application.get("interview_link_generated") or application.get("interview_link") or application.get("verification_link")),
            "interview_link_generated_at": application.get("interview_link_generated_at") or "",
            "identityConfig": identity_config,
            "identity_config": identity_config,
            "resumePhotoAvailable": identity_config["resumePhotoAvailable"],
            "resume_photo_available": identity_config["resumePhotoAvailable"],
        },
        "questions": questions,
        "question_bank_count": question_bank_count,
        "default_question_source": default_question_source,
        "filters": {
            "difficulties": ["easy", "medium", "hard"],
            "areas_of_interest": areas,
            "job_roles": job_roles,
            "tags": tags,
        },
        "interview_config": {
            **(application.get("interview_config") if isinstance(application.get("interview_config"), dict) else {}),
            "identityConfig": identity_config,
            "identity_config": identity_config,
        },
        "identityConfig": identity_config,
        "identity_config": identity_config,
        "resumePhotoAvailable": identity_config["resumePhotoAvailable"],
        "resume_photo_available": identity_config["resumePhotoAvailable"],
        "interview_questions": application.get("interview_questions") or {},
    }


@router.post("/{application_id}/configure-questions")
def configure_interview_questions(application_id: str, payload: ConfigureQuestionsRequest):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if _is_interview_completed(application):
        raise HTTPException(status_code=400, detail="Interview already completed")

    if application.get("interview_link_generated") is True or application.get("interview_link") or application.get("verification_link"):
        raise HTTPException(
            status_code=400,
            detail="Interview link has already been generated. Use Copy Link from the shortlisted candidates page.",
        )

    question_source = _normalize_question_source(payload.questionSource or payload.question_source)
    requested_count = _parse_positive_question_count(payload.questionCount if question_source == "qwen_generated" else payload.number_of_questions)

    if requested_count is None and question_source == "qwen_generated":
        requested_count = _parse_positive_question_count(payload.number_of_questions)

    if requested_count is None and question_source == "question_bank":
        requested_count = _parse_positive_question_count(payload.questionCount)

    if requested_count is None or requested_count <= 0:
        raise HTTPException(status_code=400, detail="Number of questions must be greater than zero.")

    identity_config = normalize_requested_identity_config(application, payload)

    if _identity_skip_requested(payload) and not identity_config["resumePhotoAvailable"]:
        raise HTTPException(status_code=400, detail=RESUME_PHOTO_REQUIRED_MESSAGE)

    print(
        "[Interview configure-questions] "
        f"questionSource={question_source} questionCount={requested_count} "
        f"candidateId={application_id} jobId={application.get('job_id')}"
    )

    if question_source == "qwen_generated":
        split = _difficulty_split_dict(payload.difficultySplit or payload.difficulty_split)
        split_total = sum(split.values())

        print("[Interview configure-questions] questionSource=qwen_generated questionCount=", requested_count, "difficultySplit=", split)

        if split_total <= 0:
            raise HTTPException(status_code=400, detail="At least one Qwen-generated question is required.")

        if split_total != requested_count:
            raise HTTPException(
                status_code=400,
                detail="Difficulty split must add up to the total number of interview questions.",
            )

        result = generate_qwen_interview_questions(application, split, requested_count)

        if not result.get("success"):
            bank_empty = len(load_question_bank(str(application.get("job_id") or ""))) == 0
            message = (
                "Question bank is empty and Qwen generation failed. Please add questions to the bank or try again."
                if bank_empty
                else result.get("message") or "Question generation failed. Please try again or use question bank selection."
            )
            raise HTTPException(status_code=503, detail=message)

        generated_questions = [
            _snapshot_question(question, index)
            for index, question in enumerate(result.get("questions") or [], start=1)
        ]
        configured_at = datetime.now().isoformat()
        interview_payload = {
            "success": True,
            "status": "success",
            "source": "qwen_generated",
            "question_source": "qwen_generated",
            "candidate_name": _get_candidate_name(application),
            "difficulty_split": split,
            "questions": generated_questions,
            "generatedQuestions": generated_questions,
            "generated_questions": generated_questions,
            "finalQuestions": generated_questions,
            "final_questions": generated_questions,
            "identityConfig": identity_config,
            "identity_config": identity_config,
            "configured_at": configured_at,
        }
        interview_config = {
            "number_of_questions": requested_count,
            "question_source": "qwen_generated",
            "difficulty_split": split,
            "selected_question_ids": [],
            "filters_used": payload.filters_used.model_dump(),
            "identityConfig": identity_config,
            "identity_config": identity_config,
            "configured_at": configured_at,
        }

        update_application(
            application_id,
            {
                "interview_config": interview_config,
                "interview_questions": interview_payload,
                "interviewQuestions": generated_questions,
                "generatedQuestions": generated_questions,
                "generated_questions": generated_questions,
                "finalQuestions": generated_questions,
                "final_questions": generated_questions,
                "question_source": "qwen_generated",
                "questionSource": "qwen_generated",
                "difficultySplit": split,
                "difficulty_split": split,
                "identityConfig": identity_config,
                "identity_config": identity_config,
                "total_questions": requested_count,
            },
        )

        print(
            "[Interview configure-questions] Qwen generation completed "
            f"candidateId={application_id} generatedCount={len(generated_questions)} "
            f"distribution={_question_difficulty_distribution(generated_questions)}"
        )

        return {
            "success": True,
            "interview_config": interview_config,
            "interview_questions": interview_payload,
            "identityConfig": identity_config,
            "identity_config": identity_config,
        }

    raw_selected_ids = payload.selectedQuestionIds or payload.selected_question_ids
    selected_ids = [str(question_id).strip() for question_id in raw_selected_ids if str(question_id).strip()]

    if len(set(selected_ids)) != len(selected_ids):
        raise HTTPException(status_code=400, detail="Selected questions must be unique.")

    if len(selected_ids) != requested_count:
        raise HTTPException(
            status_code=400,
            detail=f"Select exactly {requested_count} question(s) before generating the link.",
        )

    job_id = str(application.get("job_id") or "")
    bank_questions = load_question_bank(job_id)
    question_by_id = {
        str(question.get("_id") or question.get("id") or question.get("question_id")): question
        for question in bank_questions
    }
    missing_ids = [question_id for question_id in selected_ids if question_id not in question_by_id]

    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Questions not found: {', '.join(missing_ids)}")

    selected_questions = [
        _snapshot_question(question_by_id[question_id], index)
        for index, question_id in enumerate(selected_ids, start=1)
    ]
    configured_at = datetime.now().isoformat()
    filters_used = payload.filters_used.model_dump()
    interview_payload = {
        "success": True,
        "status": "success",
        "source": "question_bank",
        "question_source": "question_bank",
        "candidate_name": _get_candidate_name(application),
        "question_bank_id": job_id,
        "question_bank_name": str(application.get("job_role") or application.get("job_title") or "Question Bank"),
        "questions": selected_questions,
        "selectedQuestionIds": selected_ids,
        "selected_question_ids": selected_ids,
        "finalQuestions": selected_questions,
        "final_questions": selected_questions,
        "identityConfig": identity_config,
        "identity_config": identity_config,
        "configured_at": configured_at,
    }
    interview_config = {
        "number_of_questions": requested_count,
        "question_source": "question_bank",
        "selected_question_ids": selected_ids,
        "selectedQuestionIds": selected_ids,
        "filters_used": filters_used,
        "identityConfig": identity_config,
        "identity_config": identity_config,
        "configured_at": configured_at,
    }

    update_application(
        application_id,
        {
            "interview_config": interview_config,
            "interview_questions": interview_payload,
            "interviewQuestions": selected_questions,
            "finalQuestions": selected_questions,
            "final_questions": selected_questions,
            "question_source": "question_bank",
            "questionSource": "question_bank",
            "selectedQuestionIds": selected_ids,
            "selected_question_ids": selected_ids,
            "question_bank_id": job_id,
            "questionBankId": job_id,
            "question_bank_name": interview_payload["question_bank_name"],
            "questionBankName": interview_payload["question_bank_name"],
            "identityConfig": identity_config,
            "identity_config": identity_config,
            "total_questions": requested_count,
        },
    )

    return {
        "success": True,
        "interview_config": interview_config,
        "interview_questions": interview_payload,
        "identityConfig": identity_config,
        "identity_config": identity_config,
    }


@router.get("/{application_id}/configured-questions")
def get_configured_interview_questions(application_id: str):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    return {
        "success": True,
        "interview_config": application.get("interview_config") or {},
        "interview_questions": application.get("interview_questions") or {},
        "identityConfig": build_identity_config(application),
        "identity_config": build_identity_config(application),
    }


@router.post("/face-verify/{application_id}")
async def face_verify(application_id: str, frame: UploadFile = File(...)):
    live_frame_path = None
    reference_path = None

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

        identity_config = build_identity_config(application)
        configured_source = identity_config.get("faceVerificationSource") or GOVERNMENT_ID_SOURCE

        if configured_source == RESUME_PHOTO_SOURCE and not identity_config.get("resumePhotoAvailable"):
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "match": False,
                    "score": 0.0,
                    "threshold": DEFAULT_FACE_VERIFY_THRESHOLD,
                    "identityConfig": identity_config,
                    "identity_config": identity_config,
                    "reference_source": RESUME_PHOTO_SOURCE,
                    "message": RESUME_PHOTO_REQUIRED_MESSAGE,
                },
            )

        reference_path, reference_source, checked_paths = _find_reference_face_path(application, configured_source)
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
                    "identityConfig": identity_config,
                    "identity_config": identity_config,
                    "reference_source": configured_source,
                    "message": _missing_reference_message(configured_source),
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
                    "identityConfig": identity_config,
                    "identity_config": identity_config,
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
        result["identityConfig"] = identity_config
        result["identity_config"] = identity_config
        result["message"] = _face_verification_message(reference_source, result)
        _record_face_verification(application_id, reference_source, result)
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
    finally:
        if live_frame_path:
            Path(live_frame_path).unlink(missing_ok=True)
        if reference_path and _is_temp_path(reference_path):
            Path(reference_path).unlink(missing_ok=True)


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

    access = _build_access_response(application)

    if access["status"] != "allowed":
        raise HTTPException(status_code=403, detail=access["message"])

    if not _is_interview_access_verified(application):
        raise HTTPException(status_code=403, detail="Candidate verification is required before interview")

    questions = _prepare_interview_questions(application_id, application)
    identity_config = build_identity_config(application)
    return {
        **questions,
        "identityConfig": identity_config,
        "identity_config": identity_config,
    }


@router.get("/{application_id}/questions")
def get_candidate_interview_questions(application_id: str):
    return get_interview_questions(application_id)


@router.post("/{application_id}/start")
def start_interview(application_id: str):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    access = _build_access_response(application)

    if access["status"] == "complete":
        return {
            "success": True,
            "status": "complete",
            "interview_status": "complete",
            "interviewStatus": "complete",
            "interview_completed": True,
            "questions": [],
            "message": "Interview already completed",
        }

    if access["status"] not in {"allowed", "not_started"}:
        raise HTTPException(status_code=403, detail=access["message"])

    if not _is_interview_access_verified(application):
        raise HTTPException(status_code=403, detail="Indian Government ID and face verification are required before interview")

    if _is_interview_completed(application):
        return {
            "success": True,
            "status": "complete",
            "interview_status": "complete",
            "interviewStatus": "complete",
            "interview_completed": True,
            "questions": [],
            "message": "Interview already completed",
        }

    questions = _prepare_interview_questions(application_id, application)
    question_list = questions.get("questions") if isinstance(questions, dict) else []
    total_questions = len(question_list) if isinstance(question_list, list) else 0

    if total_questions <= 0:
        raise HTTPException(status_code=400, detail="No interview questions configured. Please contact HR.")

    schedule = _normalize_schedule(None, application)
    existing_session_id = str(application.get("interview_session_id") or "")
    session_id = existing_session_id or str(uuid.uuid4())
    now = datetime.now().isoformat()
    update_application(
        application_id,
        {
            "interview_status": "not_started",
            "interviewStatus": "not_started",
            "interview_completed": False,
            "interview_started_at": application.get("interview_started_at") or now,
            "interview_last_seen_at": now,
            "interview_session_id": session_id,
            "join_window_ends_at": (
                _join_window_end(schedule["scheduled_at"]).isoformat()
                if schedule
                else application.get("join_window_ends_at")
            ),
            "answered_count": _answered_count(application),
            "total_questions": total_questions,
        },
    )

    return {
        **questions,
        "identityConfig": build_identity_config(application),
        "identity_config": build_identity_config(application),
        "interview_status": "not_started",
        "interviewStatus": "not_started",
        "interview_session_id": session_id,
        "interview_started_at": application.get("interview_started_at") or now,
        "total_questions": total_questions,
    }


@router.post("/{application_id}/heartbeat")
def heartbeat_interview(application_id: str):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if _is_interview_completed(application):
        return {"success": True, "status": "complete"}

    update_application(application_id, {"interview_last_seen_at": datetime.now().isoformat()})
    return {"success": True, "status": _normalize_interview_status(application)}


@router.post("/{application_id}/quit")
def quit_interview(application_id: str):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if _is_interview_completed(application):
        return {"success": True, "status": "complete"}

    status = "partial" if _answered_count(application) > 0 else "not_started"
    finalized = finalize_partial_interview(application_id, status=status)

    return {
        "success": True,
        "status": finalized.get("interview_status") or status,
        "interview_score": finalized.get("interview_score", 0),
        "answered_count": finalized.get("answered_count", 0),
        "unanswered_count": finalized.get("unanswered_count", 0),
    }


@router.post("/{application_id}/answers/save")
def save_interview_answer(application_id: str, payload: AnswerSaveRequest):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    record = _upsert_saved_answer(application, payload)
    answered_count = _answered_count({"interview_answers": record["interview_answers"]})
    update_application(
        application_id,
        {
            "interview_answers": record["interview_answers"],
            "interview_status": "partial" if answered_count > 0 else "not_started",
            "interviewStatus": "partial" if answered_count > 0 else "not_started",
            "interview_completed": False,
            "interviewCompleted": False,
            "answered_count": answered_count,
            "interview_last_seen_at": datetime.now().isoformat(),
        },
    )
    return {"success": True, "answer": record["answer"]}


@router.post("/{application_id}/liveness/reference")
def save_liveness_reference(application_id: str, payload: LivenessImageRequest):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    result = _analyze_liveness_images(payload)

    if result["event_type"] != "face_match":
        liveness = _record_liveness_result(application_id, application, result, payload)
        return {
            "ok": False,
            "success": False,
            "status": result["event_type"],
            "message": result["message"],
            "liveness": _public_liveness(liveness),
        }

    liveness = _normalize_liveness(application.get("liveness"))
    liveness["reference_set"] = True
    liveness["reference_embedding"] = _embedding_to_list(result["embedding"])
    liveness["reference_set_at"] = datetime.now().isoformat()
    liveness["status"] = _liveness_status(liveness["total_warnings"], liveness["identity_mismatch_count"])
    update_application(application_id, {"liveness": liveness})

    return {
        "ok": True,
        "success": True,
        "status": "reference_set",
        "message": "Face reference captured successfully",
        "liveness": _public_liveness(liveness),
    }


@router.post("/{application_id}/liveness/check")
def check_liveness(application_id: str, payload: LivenessImageRequest):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    liveness = _normalize_liveness(application.get("liveness"))
    result = _analyze_liveness_images(payload)

    if result["event_type"] == "face_match":
        reference_embedding = liveness.get("reference_embedding")

        if not reference_embedding:
            liveness["reference_set"] = True
            liveness["reference_embedding"] = _embedding_to_list(result["embedding"])
            liveness["reference_set_at"] = datetime.now().isoformat()
            update_application(application_id, {"liveness": liveness})
            return _liveness_response(True, "passed", "face_match", None, "Face reference captured successfully", liveness)

        similarity = round(float(cosine_similarity(reference_embedding, result["embedding"])), 4)
        liveness["last_similarity"] = similarity

        if similarity >= DEFAULT_FACE_VERIFY_THRESHOLD:
            liveness["status"] = _liveness_status(liveness["total_warnings"], liveness["identity_mismatch_count"])
            update_application(application_id, {"liveness": liveness})
            return _liveness_response(True, liveness["status"], "face_match", similarity, "Face verified", liveness)

        result = {
            "event_type": "identity_mismatch",
            "message": "Candidate identity mismatch detected. Please keep the same person on camera.",
            "similarity": similarity,
        }

    liveness = _record_liveness_result(application_id, application, result, payload)
    return _liveness_response(
        False,
        liveness["status"],
        result["event_type"],
        result.get("similarity"),
        result["message"],
        liveness,
    )


@router.post("/{application_id}/complete")
def complete_interview_direct(application_id: str):
    return complete_interview(application_id)


@router.post("/{application_id}/liveness-event")
def save_liveness_event(application_id: str, payload: LivenessEventRequest):
    application = get_resume_application(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    liveness = _normalize_liveness(application.get("liveness"))
    event_type = _normalize_liveness_event_type(payload.type)

    if not event_type:
        raise HTTPException(status_code=400, detail="Invalid liveness event type")

    event = {
        "type": event_type,
        "timestamp": payload.timestamp or datetime.now().isoformat(),
        "question_index": payload.question_index,
        "message": payload.message or _liveness_message(event_type),
    }
    liveness["events"].append(event)
    liveness["total_warnings"] = len(liveness["events"])

    if event_type == "no_face_detected":
        liveness["no_face_count"] += 1
    elif event_type == "multiple_faces_detected":
        liveness["multiple_face_count"] += 1
    elif event_type == "identity_mismatch":
        liveness["identity_mismatch_count"] += 1

    liveness["status"] = _liveness_status(liveness["total_warnings"], liveness["identity_mismatch_count"])
    update_application(application_id, {"liveness": liveness})

    return {
        "success": True,
        "liveness": _public_liveness(liveness),
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

    try:
        result = transcribe_audio(audio_path)

        if not result.get("success"):
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "success": False,
                    "message": result.get("message", "Whisper transcription failed"),
                    "audioPath": "",
                    "audio_path": "",
                    "model": result.get("model"),
                },
            )

        transcript = result.get("transcript", "")
        print(f"[Interview transcribe] transcript length={len(transcript)}")
        return {
            "status": "success",
            "success": True,
            "transcript": transcript,
            "audioPath": "",
            "audio_path": "",
            "model": result.get("model"),
        }
    finally:
        audio_path.unlink(missing_ok=True)


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
    raw_record = _upsert_saved_answer(
        application,
        AnswerSaveRequest(
            question_index=(question_index or 0) + 1,
            question_id=request.question_id,
            question=question.get("question", ""),
            expected_answer=question.get("expected_answer") or question.get("expectedAnswer") or "",
            candidate_answer=final_answer,
            status="submitted",
        ),
    )
    raw_save_success = update_application(
        application_id,
        {
            "interview_answers": raw_record["interview_answers"],
            "interview_status": "partial",
            "interviewStatus": "partial",
            "interview_completed": False,
            "answered_count": _answered_count({"interview_answers": raw_record["interview_answers"]}),
            "interview_last_seen_at": datetime.now().isoformat(),
        },
    )

    if not raw_save_success:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "success": False,
                "message": "Could not save raw answer. Please retry submission.",
                "reason": "MongoDB save failed",
            },
        )

    application = {**application, "interview_answers": raw_record["interview_answers"]}

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
    answer_record["question_index"] = (question_index or 0) + 1
    answer_record["submittedAt"] = raw_record["answer"].get("submittedAt") or answer_record["submittedAt"]
    answer_record["submitted_at"] = raw_record["answer"].get("submitted_at") or answer_record["submitted_at"]

    if evaluation.get("success") is True:
        answer_record["status"] = "evaluated"
        answer_record["answer_status"] = "evaluated"
        answer_record["evaluated_at"] = datetime.now().isoformat()
    else:
        answer_record["status"] = "failed"
        answer_record["answer_status"] = "failed"
        answer_record["failed_at"] = datetime.now().isoformat()

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
            "interview_status": "partial",
            "interviewStatus": "partial",
            "interview_completed": False,
            "interview_score": current_score,
            "answered_count": _answered_count({"interview_answers": interview_answers}),
            "interview_last_seen_at": datetime.now().isoformat(),
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
        if isinstance(answer, dict) and answer.get("archived") is not True and _get_grading_status(answer) == "graded"
    ]
    average_score = round(sum(scores) / len(scores), 1) if scores else 0
    updates = {
        "interview_answers": interview_answers,
        "interview_status": "complete",
        "interviewStatus": "complete",
        "interview_completed": True,
        "interviewCompleted": True,
        "interview_score": average_score,
        "interview_completed_at": datetime.now().isoformat(),
        "completedAt": datetime.now().isoformat(),
        "answered_count": _answered_count({"interview_answers": interview_answers}),
        "total_questions": len(questions),
    }
    updates["interview_attempts"] = _upsert_attempt_snapshot(
        application.get("interview_attempts"),
        _current_attempt_snapshot({**application, **updates}, "complete", updates["interview_completed_at"]),
    )

    token = get_interview_link_token(application)

    if token:
        _mark_link_used(token)

    update_application(application_id, updates)

    return {
        "success": True,
        "interview_status": "complete",
        "interview_score": average_score,
        "answered_count": _answered_count({"interview_answers": interview_answers}),
        "total_questions": len(questions),
    }


def _find_reference_face_path(application: dict, preferred_source: str | None = None):
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

    if preferred_source == RESUME_PHOTO_SOURCE:
        for candidate in resume_candidates:
            resolved_path = _existing_path(candidate, checked_paths, RESUME_PHOTO_SOURCE)

            if resolved_path:
                print("[Interview face-verify] selected_reference_source=resume_photo")
                return resolved_path, RESUME_PHOTO_SOURCE, checked_paths

        print("[Interview face-verify] selected_reference_source=none")
        return None, RESUME_PHOTO_SOURCE, checked_paths

    for candidate in aadhaar_candidates:
        resolved_path = _existing_path(candidate, checked_paths, GOVERNMENT_ID_SOURCE)

        if resolved_path:
            print("[Interview face-verify] selected_reference_source=government_id")
            return resolved_path, GOVERNMENT_ID_SOURCE, checked_paths

    if preferred_source == GOVERNMENT_ID_SOURCE:
        print("[Interview face-verify] selected_reference_source=none")
        return None, GOVERNMENT_ID_SOURCE, checked_paths

    for candidate in resume_candidates:
        resolved_path = _existing_path(candidate, checked_paths, RESUME_PHOTO_SOURCE)

        if resolved_path:
            print("[Interview face-verify] selected_reference_source=resume_photo")
            return resolved_path, RESUME_PHOTO_SOURCE, checked_paths

    for candidate in candidate_image_candidates:
        resolved_path = _existing_path(candidate, checked_paths, "candidate_image")

        if resolved_path:
            print("[Interview face-verify] selected_reference_source=candidate_image")
            return resolved_path, "candidate_image", checked_paths

    print("[Interview face-verify] selected_reference_source=none")
    return None, None, checked_paths


def _missing_reference_message(source: str | None) -> str:
    if source == RESUME_PHOTO_SOURCE:
        return RESUME_PHOTO_REQUIRED_MESSAGE

    return "Indian Government ID photo is not available. Please complete Indian Government ID verification."


def _face_verification_message(reference_source: str | None, result: dict) -> str:
    matched = result.get("match") is True or result.get("verified") is True

    if reference_source == RESUME_PHOTO_SOURCE:
        return "Candidate face matched resume photo" if matched else "Face verification failed against resume photo."

    if reference_source == GOVERNMENT_ID_SOURCE:
        return "Candidate face matched government ID photo" if matched else "Face verification failed against government ID photo."

    return result.get("message") or ("Face verification passed" if matched else "Face verification failed.")


def _record_face_verification(application_id: str, source: str | None, result: dict) -> None:
    matched = result.get("match") is True or result.get("verified") is True
    now = datetime.now().isoformat()
    face_verification = {
        "source": source or "",
        "status": "passed" if matched else "failed",
        "score": result.get("score"),
        "threshold": result.get("threshold", DEFAULT_FACE_VERIFY_THRESHOLD),
        "verifiedAt": now if matched else "",
        "checkedAt": now,
        "message": result.get("message") or _face_verification_message(source, result),
    }
    update_application(
        application_id,
        {
            "faceVerification": face_verification,
            "face_verification": face_verification,
            "live_face_verification": face_verification,
            "faceReferenceSource": source or "",
        },
    )


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

    path_text = str(path_value)

    if path_text.startswith("gridfs://"):
        materialized = materialize_file_from_mongo(path_text.replace("gridfs://", "", 1))

        if materialized and materialized.exists():
            _record_checked_path(checked_paths, source, path_value, materialized, True)
            return materialized

    candidate = Path(path_text).expanduser()

    if candidate.exists():
        _record_checked_path(checked_paths, source, path_value, candidate, True)
        return candidate

    relative_candidate = PROJECT_ROOT / candidate

    if relative_candidate.exists():
        _record_checked_path(checked_paths, source, path_value, relative_candidate, True)
        return relative_candidate

    app_relative_candidate = APP_ROOT / candidate

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


def _get_configured_question_payload(application: dict) -> dict | None:
    question_payload = application.get("interview_questions")

    if isinstance(question_payload, dict) and _has_current_question_contract(question_payload):
        questions = question_payload.get("questions")

        if isinstance(questions, list) and questions:
            config = application.get("interview_config") if isinstance(application.get("interview_config"), dict) else {}
            configured_count = int(config.get("number_of_questions") or application.get("total_questions") or len(questions))

            if len(questions) != configured_count:
                return None

            return question_payload

    return None


def _build_interview_configuration(application_id: str, application: dict, payload: ConfigureQuestionsRequest) -> dict:
    question_source = _normalize_question_source(payload.questionSource or payload.question_source)
    requested_count = _parse_positive_question_count(payload.questionCount if question_source == "qwen_generated" else payload.number_of_questions)

    if requested_count is None:
        requested_count = _parse_positive_question_count(payload.number_of_questions or payload.questionCount)

    if requested_count is None or requested_count <= 0:
        raise HTTPException(status_code=400, detail="Number of questions must be greater than zero.")

    identity_config = normalize_requested_identity_config(application, payload)

    if _identity_skip_requested(payload) and not identity_config["resumePhotoAvailable"]:
        raise HTTPException(status_code=400, detail=RESUME_PHOTO_REQUIRED_MESSAGE)

    filters_used = payload.filters_used.model_dump() if hasattr(payload.filters_used, "model_dump") else {}
    configured_at = datetime.now().isoformat()

    if question_source == "qwen_generated":
        split = _difficulty_split_dict(payload.difficultySplit or payload.difficulty_split)
        split_total = sum(split.values())

        if split_total <= 0:
            raise HTTPException(status_code=400, detail="At least one Qwen-generated question is required.")

        if split_total != requested_count:
            raise HTTPException(
                status_code=400,
                detail="Difficulty split must add up to the total number of interview questions.",
            )

        result = generate_qwen_interview_questions(application, split, requested_count)

        if not result.get("success"):
            bank_empty = len(load_question_bank(str(application.get("job_id") or ""))) == 0
            message = (
                "Question bank is empty and Qwen generation failed. Please add questions to the bank or try again."
                if bank_empty
                else result.get("message") or "Question generation failed. Please try again or use question bank selection."
            )
            raise HTTPException(status_code=503, detail=message)

        generated_questions = [
            _snapshot_question(question, index)
            for index, question in enumerate(result.get("questions") or [], start=1)
        ]
        interview_payload = {
            "success": True,
            "status": "success",
            "source": "qwen_generated",
            "question_source": "qwen_generated",
            "candidate_name": _get_candidate_name(application),
            "difficulty_split": split,
            "questions": generated_questions,
            "generatedQuestions": generated_questions,
            "generated_questions": generated_questions,
            "finalQuestions": generated_questions,
            "final_questions": generated_questions,
            "identityConfig": identity_config,
            "identity_config": identity_config,
            "configured_at": configured_at,
        }
        interview_config = {
            "number_of_questions": requested_count,
            "question_source": "qwen_generated",
            "difficulty_split": split,
            "selected_question_ids": [],
            "filters_used": filters_used,
            "identityConfig": identity_config,
            "identity_config": identity_config,
            "configured_at": configured_at,
        }
        return {
            "question_source": "qwen_generated",
            "requested_count": requested_count,
            "selected_ids": [],
            "difficulty_split": split,
            "questions": generated_questions,
            "interview_payload": interview_payload,
            "interview_config": interview_config,
            "identity_config": identity_config,
        }

    raw_selected_ids = payload.selectedQuestionIds or payload.selected_question_ids
    selected_ids = [str(question_id).strip() for question_id in raw_selected_ids if str(question_id).strip()]

    if len(set(selected_ids)) != len(selected_ids):
        raise HTTPException(status_code=400, detail="Selected questions must be unique.")

    if len(selected_ids) != requested_count:
        raise HTTPException(
            status_code=400,
            detail=f"Select exactly {requested_count} question(s) before generating the link.",
        )

    job_id = str(application.get("job_id") or application.get("jobId") or "")
    bank_questions = load_question_bank(job_id)
    question_by_id = {
        str(question.get("_id") or question.get("id") or question.get("question_id")): question
        for question in bank_questions
    }
    missing_ids = [question_id for question_id in selected_ids if question_id not in question_by_id]

    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Questions not found: {', '.join(missing_ids)}")

    selected_questions = [
        _snapshot_question(question_by_id[question_id], index)
        for index, question_id in enumerate(selected_ids, start=1)
    ]
    interview_payload = {
        "success": True,
        "status": "success",
        "source": "question_bank",
        "question_source": "question_bank",
        "candidate_name": _get_candidate_name(application),
        "question_bank_id": job_id,
        "question_bank_name": str(application.get("job_role") or application.get("job_title") or "Question Bank"),
        "questions": selected_questions,
        "selectedQuestionIds": selected_ids,
        "selected_question_ids": selected_ids,
        "finalQuestions": selected_questions,
        "final_questions": selected_questions,
        "identityConfig": identity_config,
        "identity_config": identity_config,
        "configured_at": configured_at,
    }
    interview_config = {
        "number_of_questions": requested_count,
        "question_source": "question_bank",
        "selected_question_ids": selected_ids,
        "selectedQuestionIds": selected_ids,
        "filters_used": filters_used,
        "identityConfig": identity_config,
        "identity_config": identity_config,
        "configured_at": configured_at,
    }

    return {
        "question_source": "question_bank",
        "requested_count": requested_count,
        "selected_ids": selected_ids,
        "difficulty_split": {},
        "questions": selected_questions,
        "interview_payload": interview_payload,
        "interview_config": interview_config,
        "identity_config": identity_config,
    }


def _normalize_question_source(value: str) -> str:
    source = str(value or "question_bank").strip().lower()
    return "qwen_generated" if source in {"qwen", "qwen_generated", "ai", "ai_generated"} else "question_bank"


def _parse_positive_question_count(value) -> int | None:
    if isinstance(value, bool) or value is None:
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value) if value.is_integer() else None

    text = str(value).strip()

    if not text or not text.isdigit():
        return None

    return int(text)


def _difficulty_split_dict(split: DifficultySplit | dict | None) -> dict:
    data = split.model_dump() if hasattr(split, "model_dump") else (split if isinstance(split, dict) else {})
    normalized = {}

    for difficulty in ("easy", "medium", "hard"):
        value = data.get(difficulty, 0)

        if isinstance(value, bool):
            raise HTTPException(status_code=400, detail="Difficulty split values must be integers.")

        if isinstance(value, int):
            count = value
        elif isinstance(value, float):
            if not value.is_integer():
                raise HTTPException(status_code=400, detail="Difficulty split values must be integers.")
            count = int(value)
        else:
            text = str(value or "").strip()
            if not text:
                count = 0
            elif text.isdigit():
                count = int(text)
            else:
                raise HTTPException(status_code=400, detail="Difficulty split values must be integers.")

        if not isinstance(count, int):
            raise HTTPException(status_code=400, detail="Difficulty split values must be integers.")

        if count < 0:
            raise HTTPException(status_code=400, detail="Difficulty split values cannot be negative.")

        normalized[difficulty] = count

    return normalized


def _identity_skip_requested(payload: ConfigureQuestionsRequest) -> bool:
    requested = payload.identityConfig or payload.identity_config

    if hasattr(requested, "model_dump"):
        requested = requested.model_dump()

    requested = requested if isinstance(requested, dict) else {}

    if payload.identityVerificationRequired is False or payload.identity_verification_required is False:
        return True

    if requested.get("requireGovernmentId") is False or requested.get("require_government_id") is False:
        return True

    source = requested.get("faceVerificationSource") or requested.get("face_verification_source")
    return str(source or "").strip().lower() in {"resume", "resume_face", "resume_photo"}


def _question_difficulty_distribution(questions: list[dict]) -> dict:
    return {
        difficulty: len([
            question
            for question in questions
            if str(question.get("difficulty") or "").lower() == difficulty
        ])
        for difficulty in ("easy", "medium", "hard")
    }


def _snapshot_question(question: dict, index: int) -> dict:
    question_id = str(question.get("_id") or question.get("id") or question.get("question_id") or f"q{index}")
    expected_answer = str(question.get("expected_answer") or question.get("expectedAnswer") or "N/A").strip() or "N/A"
    area = str(
        question.get("area_of_interest")
        or question.get("areaOfInterest")
        or question.get("category")
        or question.get("topic")
        or "General"
    ).strip() or "General"

    return {
        "id": f"q{index}",
        "question_id": question_id,
        "question_index": index,
        "question": str(question.get("question") or "").strip(),
        "expected_answer": expected_answer,
        "expectedAnswer": expected_answer,
        "difficulty": str(question.get("difficulty") or "medium").strip().lower() or "medium",
        "area_of_interest": area,
        "areaOfInterest": area,
        "category": area,
        "tags": question.get("tags") if isinstance(question.get("tags"), list) else [],
        "job_role": str(question.get("job_role") or question.get("jobRole") or "").strip(),
        "score_weight": question.get("score_weight") or question.get("scoreWeight") or 1,
        "source": question.get("source") or question.get("question_source") or "",
    }


def _prepare_interview_questions(application_id: str, application: dict) -> dict:
    existing_questions = application.get("interview_questions")

    if isinstance(existing_questions, dict) and _has_current_question_contract(existing_questions):
        _log_question_load(application, existing_questions)
        return existing_questions

    result = {
        "success": True,
        "status": "empty",
        "source": "none",
        "question_source": "none",
        "candidate_name": _get_candidate_name(application),
        "questions": [],
        "message": "No interview questions configured. Please contact HR.",
    }
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
                "id": str(item.get("id") or item.get("_id") or item.get("question_id") or f"q{len(normalized) + 1}"),
                "question_id": str(item.get("question_id") or item.get("_id") or item.get("id") or f"q{len(normalized) + 1}"),
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
                "area_of_interest": str(
                    item.get("area_of_interest")
                    or item.get("areaOfInterest")
                    or item.get("category")
                    or item.get("topic")
                    or "General"
                ).strip(),
                "tags": item.get("tags") if isinstance(item.get("tags"), list) else [],
                "job_role": str(item.get("job_role") or item.get("jobRole") or "").strip(),
                "score_weight": item.get("score_weight") or item.get("scoreWeight") or 1,
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


def _is_temp_path(path_value) -> bool:
    try:
        path = Path(path_value).resolve()
        temp_root = get_path("temp_dir").resolve()
    except Exception:
        return False

    return path == temp_root or temp_root in path.parents


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
        "area_of_interest": question.get("area_of_interest") or question.get("areaOfInterest") or question.get("category") or "N/A",
        "areaOfInterest": question.get("area_of_interest") or question.get("areaOfInterest") or question.get("category") or "N/A",
        "tags": question.get("tags") if isinstance(question.get("tags"), list) else [],
        "job_role": question.get("job_role") or question.get("jobRole") or "",
        "score_weight": question.get("score_weight") or question.get("scoreWeight") or 1,
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


def finalize_partial_interview(application_id: str, status: str | None = None) -> dict:
    application = get_resume_application(application_id)

    if not application:
        return {}

    question_payload = application.get("interview_questions") or {}
    questions = question_payload.get("questions") if isinstance(question_payload, dict) else []

    if not isinstance(questions, list):
        questions = []

    interview_answers = application.get("interview_answers")

    if not isinstance(interview_answers, dict):
        interview_answers = {}

    normalized_answers = dict(interview_answers)
    now = datetime.now().isoformat()

    for index, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            continue

        question_id = str(question.get("id") or question.get("question_id") or f"q{index}")

        if not question_id or _has_saved_answer(normalized_answers.get(question_id)):
            continue

        normalized_answers[question_id] = _unanswered_answer_record(question, index, question_id, now)

    answered_count = _answered_count({"interview_answers": normalized_answers})
    total_questions = len([question for question in questions if isinstance(question, dict)])
    unanswered_count = max(total_questions - answered_count, 0)
    finalized_status = _normalize_status_value(status or application.get("interview_status") or application.get("interviewStatus"), application)

    if finalized_status not in {"partial", "not_started"}:
        finalized_status = "partial" if answered_count > 0 else "not_started"

    average_score = _average_configured_answer_scores(normalized_answers, total_questions)
    updates = {
        "interview_answers": normalized_answers,
        "interview_status": finalized_status,
        "interviewStatus": finalized_status,
        "interview_completed": False,
        "interviewCompleted": False,
        "interview_score": average_score,
        "average_interview_score": average_score,
        "answered_count": answered_count,
        "unanswered_count": unanswered_count,
        "total_questions": total_questions,
        "interview_quit_at": application.get("interview_quit_at") or now,
        "interview_last_seen_at": now,
    }
    updates["interview_attempts"] = _upsert_attempt_snapshot(
        application.get("interview_attempts"),
        _current_attempt_snapshot({**application, **updates}, finalized_status, now),
    )
    update_application(application_id, updates)

    return {**application, **updates}


def _normalize_status_value(value, application: dict | None = None) -> str:
    status = str(value or "").strip().lower()

    if status in {"complete", "completed"}:
        return "complete"

    if status in {"partial", "abandoned", "quit", "quit_midway", "interrupted"}:
        return "partial"

    if status in {"not_started", "not started", "link_created", "configured", "pending", ""}:
        return "not_started"

    if status == "in_progress":
        return "partial" if _answered_count(application or {}) > 0 else "not_started"

    return "not_started"


def _normalize_interview_status(application: dict | None) -> str:
    if not isinstance(application, dict):
        return "not_started"

    total_questions = _configured_question_count(application)

    if _has_completion_marker(application) or (total_questions > 0 and _answered_count(application) >= total_questions):
        return "complete"

    return _normalize_status_value(
        application.get("interview_status") or application.get("interviewStatus"),
        application,
    )


def _next_attempt_number(application: dict) -> int:
    return _current_attempt_number(application) + 1


def _current_attempt_number(application: dict) -> int:
    attempts = _attempt_history(application)
    numbers = [
        int(attempt.get("attempt_number") or 0)
        for attempt in attempts
        if isinstance(attempt, dict) and str(attempt.get("attempt_number") or "").isdigit()
    ]
    current_number = application.get("attempt_number")

    try:
        numbers.append(int(current_number or 0))
    except (TypeError, ValueError):
        pass

    return max(numbers or [0]) or 1


def _attempt_history(application: dict | list | None) -> list[dict]:
    if isinstance(application, list):
        raw_attempts = application
    elif isinstance(application, dict):
        raw_attempts = application.get("interview_attempts") or application.get("interviewAttempts") or []
    else:
        raw_attempts = []

    return [attempt for attempt in raw_attempts if isinstance(attempt, dict)]


def _archive_current_attempt(application: dict, status: str | None = None) -> list[dict]:
    attempts = _attempt_history(application)
    snapshot = _current_attempt_snapshot(application, status)

    if not snapshot:
        return attempts

    return _upsert_attempt_snapshot(attempts, snapshot)


def _upsert_attempt_snapshot(attempts_value, snapshot: dict) -> list[dict]:
    attempts = _attempt_history(attempts_value)
    attempt_id = str(snapshot.get("attempt_id") or "")
    replaced = False
    next_attempts = []

    for attempt in attempts:
        if attempt_id and str(attempt.get("attempt_id") or "") == attempt_id:
            next_attempts.append({**attempt, **snapshot})
            replaced = True
        else:
            next_attempts.append(attempt)

    if not replaced:
        next_attempts.append(snapshot)

    return sorted(next_attempts, key=_attempt_sort_key)


def _current_attempt_snapshot(application: dict, status: str | None = None, timestamp: str | None = None) -> dict:
    normalized_status = _normalize_status_value(status or application.get("interview_status"), application)
    answers = application.get("interview_answers") if isinstance(application.get("interview_answers"), dict) else {}
    has_link = bool(application.get("interview_link") or application.get("verification_link") or get_interview_link_token(application))
    has_answers = bool(answers)
    has_started = bool(application.get("interview_started_at") or application.get("interview_completed_at") or application.get("interview_quit_at"))

    if not (has_link or has_answers or has_started or normalized_status in {"partial", "complete"}):
        return {}

    now = timestamp or datetime.now().isoformat()
    attempt_id = str(
        application.get("active_attempt_id")
        or application.get("interview_session_id")
        or get_interview_link_token(application)
        or f"attempt-{application.get('attempt_number') or 1}"
    )
    try:
        attempt_number = int(application.get("attempt_number") or 1)
    except (TypeError, ValueError):
        attempt_number = 1
    question_payload = application.get("interview_questions") if isinstance(application.get("interview_questions"), dict) else {}
    questions = question_payload.get("questions") if isinstance(question_payload.get("questions"), list) else []
    answered_count = _answered_count({"interview_answers": answers})
    total_questions = int(application.get("total_questions") or len(questions) or 0)

    return {
        "attempt_id": attempt_id,
        "attempt_number": attempt_number,
        "status": normalized_status,
        "interview_status": normalized_status,
        "interview_answers": answers,
        "interview_questions": question_payload,
        "question_source": application.get("question_source") or application.get("questionSource") or "",
        "interview_score": application.get("interview_score") or application.get("interviewScore") or 0,
        "answered_count": answered_count,
        "total_questions": total_questions,
        "interview_link": application.get("interview_link") or application.get("verification_link") or "",
        "interview_token": get_interview_link_token(application),
        "interview_started_at": application.get("interview_started_at"),
        "interview_completed_at": application.get("interview_completed_at") or application.get("completedAt"),
        "interview_quit_at": application.get("interview_quit_at"),
        "created_at": application.get("interview_link_generated_at") or application.get("createdAt") or now,
        "updated_at": now,
        "report_ready": normalized_status in {"partial", "complete"},
    }


def _attempt_sort_key(attempt: dict):
    number = attempt.get("attempt_number") or 0

    try:
        number = int(number)
    except (TypeError, ValueError):
        number = 0

    timestamp = (
        attempt.get("interview_completed_at")
        or attempt.get("interview_quit_at")
        or attempt.get("updated_at")
        or attempt.get("created_at")
        or ""
    )
    return (number, str(timestamp))


def select_report_application(application: dict) -> dict | None:
    if not isinstance(application, dict):
        return None

    report_attempts = []
    current_status = _normalize_interview_status(application)

    if current_status in {"partial", "complete"}:
        current_snapshot = _current_attempt_snapshot(application, current_status)
        if current_snapshot:
            report_attempts.append(current_snapshot)

    report_attempts.extend([
        attempt
        for attempt in _attempt_history(application)
        if _normalize_status_value(attempt.get("status") or attempt.get("interview_status"), attempt) in {"partial", "complete"}
    ])

    complete_attempts = [
        attempt
        for attempt in report_attempts
        if _normalize_status_value(attempt.get("status") or attempt.get("interview_status"), attempt) == "complete"
    ]
    partial_attempts = [
        attempt
        for attempt in report_attempts
        if _normalize_status_value(attempt.get("status") or attempt.get("interview_status"), attempt) == "partial"
    ]
    selected = None

    if complete_attempts:
        selected = sorted(complete_attempts, key=_attempt_sort_key)[-1]
    elif partial_attempts:
        selected = sorted(partial_attempts, key=_attempt_sort_key)[-1]

    if not selected:
        return None

    status = _normalize_status_value(selected.get("status") or selected.get("interview_status"), selected)
    return {
        **application,
        **selected,
        "interview_status": status,
        "interviewStatus": status,
        "interview_completed": status == "complete",
        "interviewCompleted": status == "complete",
        "report_source_attempt_id": selected.get("attempt_id"),
        "report_source_attempt_number": selected.get("attempt_number"),
    }


def with_public_interview_fields(application: dict) -> dict:
    if not isinstance(application, dict):
        return application

    status = _normalize_interview_status(application)
    report_application = select_report_application(application)
    answered_count = _answered_count(application)
    total_questions = _configured_question_count(application)
    completed_at = application.get("interview_completed_at") or application.get("completedAt") or application.get("completed_at")
    completed = _is_interview_completed(application)
    interview_token = get_interview_link_token(application) or str(application.get("active_attempt_id") or application.get("currentInterviewId") or "").strip()
    application_id = str(application.get("application_id") or application.get("candidateId") or "").strip()
    job_id = application.get("jobId") or application.get("job_id") or ""
    interview_id = str(application.get("currentInterviewId") or application.get("active_attempt_id") or application.get("interviewId") or application.get("interview_id") or interview_token or "").strip()
    scheduled = _has_scheduled_interview(application)
    interview_link = (
        application.get("interviewLink")
        or application.get("interview_link")
        or application.get("verification_link")
        or _build_candidate_interview_link(application_id, interview_token)
    )
    return {
        **application,
        "candidateId": application_id,
        "jobId": job_id,
        "interviewId": interview_id,
        "interviewLinkToken": interview_token,
        "interviewLink": interview_link,
        "interview_status": status,
        "interviewStatus": status,
        "latestInterviewStatus": status,
        "answeredCount": answered_count,
        "totalQuestions": total_questions,
        "scheduledAt": application.get("scheduledAt") or application.get("scheduled_at") or application.get("interview_scheduled_at") or "",
        "configuredAt": _configured_at(application),
        "interview_completed": completed,
        "interviewCompleted": completed,
        "answeredCount": answered_count,
        "answered_count": answered_count,
        "totalQuestions": total_questions,
        "total_questions": total_questions,
        "completedAt": completed_at,
        "completed_at": completed_at,
        "canReschedule": scheduled and not completed,
        "can_reschedule": scheduled and not completed,
        "report_available": report_application is not None,
        "has_report": report_application is not None,
        "report_status": report_application.get("interview_status") if report_application else "",
        "report_source_attempt_id": report_application.get("report_source_attempt_id") if report_application else "",
        "report_source_attempt_number": report_application.get("report_source_attempt_number") if report_application else None,
    }


def _has_scheduled_interview(application: dict) -> bool:
    if not isinstance(application, dict):
        return False

    final_questions = application.get("finalQuestions") or application.get("final_questions")
    question_payload = application.get("interview_questions") if isinstance(application.get("interview_questions"), dict) else {}
    payload_questions = question_payload.get("questions") if isinstance(question_payload.get("questions"), list) else []

    return bool(
        get_interview_link_token(application)
        or application.get("interviewLink")
        or application.get("interview_link")
        or application.get("verification_link")
        or application.get("link")
        or application.get("interview_link_generated")
        or application.get("linkGenerated")
        or application.get("scheduledAt")
        or application.get("scheduled_at")
        or application.get("interview_scheduled_at")
        or _configured_at(application)
        or (isinstance(final_questions, list) and len(final_questions) > 0)
        or len(payload_questions) > 0
    )


def _configured_at(application: dict) -> str:
    config = application.get("interview_config") if isinstance(application.get("interview_config"), dict) else {}
    questions = application.get("interview_questions") if isinstance(application.get("interview_questions"), dict) else {}
    return str(
        application.get("configuredAt")
        or application.get("configured_at")
        or config.get("configured_at")
        or config.get("configuredAt")
        or questions.get("configured_at")
        or questions.get("configuredAt")
        or ""
    )


def _build_candidate_interview_link(application_id: str, token: str) -> str:
    if not application_id or not token:
        return ""

    frontend_base_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
    return f"{frontend_base_url}/verify/{application_id}?attempt={token}"


def _unanswered_answer_record(question: dict, index: int, question_id: str, timestamp: str) -> dict:
    expected_answer = question.get("expected_answer") or question.get("expectedAnswer") or "N/A"
    area = question.get("area_of_interest") or question.get("areaOfInterest") or question.get("category") or "N/A"

    return {
        "questionId": question_id,
        "question_id": question_id,
        "question_index": index,
        "question": question.get("question") or "",
        "expectedAnswer": expected_answer,
        "expected_answer": expected_answer,
        "difficulty": question.get("difficulty") or "N/A",
        "area_of_interest": area,
        "areaOfInterest": area,
        "category": area,
        "tags": question.get("tags") if isinstance(question.get("tags"), list) else [],
        "job_role": question.get("job_role") or question.get("jobRole") or "",
        "score_weight": question.get("score_weight") or question.get("scoreWeight") or 1,
        "candidate_answer": "Not answered",
        "answerText": "Not answered",
        "answer_text": "Not answered",
        "transcript": "Not answered",
        "score": 0,
        "finalScore": 0,
        "final_score": 0,
        "relevance": 0,
        "technical": 0,
        "depth": 0,
        "clarity": 0,
        "feedback": "Candidate did not answer this question.",
        "missingPoints": [],
        "missing_points": [],
        "status": "unanswered",
        "answer_status": "unanswered",
        "gradingStatus": "unanswered",
        "grading_status": "unanswered",
        "submittedAt": timestamp,
        "submitted_at": timestamp,
        "grading": {
            "finalScore": 0,
            "relevance": 0,
            "technical": 0,
            "depth": 0,
            "clarity": 0,
            "feedback": "Candidate did not answer this question.",
            "missingPoints": [],
        },
        "evaluation": {
            "success": True,
            "feedback": "Candidate did not answer this question.",
        },
    }


def _has_saved_answer(answer) -> bool:
    if not isinstance(answer, dict):
        return False

    if answer.get("archived") is True:
        return False

    text = str(
        answer.get("transcript")
        or answer.get("answerText")
        or answer.get("answer_text")
        or answer.get("candidate_answer")
        or ""
    ).strip()

    return bool(text)


def _average_configured_answer_scores(interview_answers: dict, total_questions: int) -> float:
    if total_questions <= 0:
        return _average_answer_scores(interview_answers)

    scores = [
        _extract_score(answer)
        for answer in interview_answers.values()
        if isinstance(answer, dict) and answer.get("archived") is not True
    ]

    if len(scores) < total_questions:
        scores.extend([0] * (total_questions - len(scores)))

    return round(sum(scores[:total_questions]) / total_questions, 1)


def _average_answer_scores(interview_answers: dict) -> float:
    scores = [
        _extract_score(answer)
        for answer in interview_answers.values()
        if isinstance(answer, dict) and answer.get("archived") is not True and _get_grading_status(answer) == "graded"
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
    if not isinstance(application, dict):
        return False

    if _has_completion_marker(application):
        return True

    total_questions = _configured_question_count(application)
    return total_questions > 0 and _answered_count(application) >= total_questions


def _has_completion_marker(application: dict) -> bool:
    if not isinstance(application, dict):
        return False

    status = str(
        application.get("interview_status")
        or application.get("interviewStatus")
        or application.get("status")
        or ""
    ).strip().lower()
    report_status = str(
        application.get("report_status")
        or application.get("reportStatus")
        or application.get("final_report_status")
        or application.get("finalReportStatus")
        or ""
    ).strip().lower()

    return (
        application.get("interview_completed") is True
        or application.get("interviewCompleted") is True
        or bool(application.get("interview_completed_at") or application.get("completedAt") or application.get("completed_at"))
        or status in {"complete", "completed"}
        or report_status in {"complete", "completed"}
        or application.get("completed_report_generated") is True
        or application.get("completedReportGenerated") is True
    )


def _configured_question_count(application: dict) -> int:
    if not isinstance(application, dict):
        return 0

    for key in ("finalQuestions", "final_questions"):
        questions = application.get(key)

        if isinstance(questions, list):
            return len([question for question in questions if isinstance(question, dict)])

    question_payload = application.get("interview_questions") if isinstance(application.get("interview_questions"), dict) else {}
    questions = question_payload.get("questions") if isinstance(question_payload.get("questions"), list) else []

    if questions:
        return len([question for question in questions if isinstance(question, dict)])

    try:
        return int(application.get("total_questions") or application.get("questionCount") or application.get("question_count") or 0)
    except (TypeError, ValueError):
        return 0


def _can_reschedule_interview(application: dict) -> tuple[bool, str]:
    if _is_interview_completed(application):
        return False, "Completed interviews cannot be rescheduled."

    if not _has_scheduled_interview(application):
        return False, "Interview has not been scheduled yet."

    return True, ""


def _is_verification_completed(application: dict) -> bool:
    return (
        application.get("verification_completed") is True
        or str(application.get("verification_status") or "").lower() == "verified"
    )


def _is_interview_access_verified(application: dict) -> bool:
    if not requires_government_id(application):
        return _is_face_verified(application)

    return _is_aadhaar_verified(application) and _is_face_verified(application)


def _is_aadhaar_verified(application: dict) -> bool:
    identity = application.get("identityVerification") or application.get("identity_verification") or {}
    explicit_government_id_passed = (
        application.get("aadhaarVerified") is True
        or application.get("aadhaar_verified") is True
        or application.get("governmentIdVerified") is True
        or application.get("government_id_verified") is True
        or identity.get("isValidIndianGovId") is True
        or identity.get("is_valid_indian_gov_id") is True
        or str(application.get("verificationStatus") or "").lower() in {"aadhaar_passed", "government_id_passed", "identity_passed"}
        or str(application.get("verification_status") or "").lower() in {"aadhaar_passed", "government_id_passed", "identity_passed"}
    )

    if not requires_government_id(application):
        return explicit_government_id_passed

    return (
        explicit_government_id_passed
        or str(application.get("verificationStatus") or "").lower() == "verified"
        or str(application.get("verification_status") or "").lower() == "verified"
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


def _normalize_schedule(payload: CreateInterviewLinkRequest | None, application: dict) -> dict | None:
    scheduled_at = None

    if payload and payload.interview_scheduled_at:
        scheduled_at = _parse_datetime(payload.interview_scheduled_at)

    interview_date = (payload.interview_date if payload else None) or application.get("interview_date")
    interview_time = (payload.interview_time if payload else None) or application.get("interview_time")

    if scheduled_at is None and interview_date and interview_time:
        scheduled_at = _parse_datetime(f"{interview_date}T{interview_time}")

    if scheduled_at is None:
        scheduled_at = _parse_datetime(str(application.get("interview_scheduled_at") or ""))

    if scheduled_at is None:
        return None

    return {
        "date": scheduled_at.date().isoformat(),
        "time": scheduled_at.strftime("%H:%M"),
        "scheduled_at": scheduled_at.replace(second=0, microsecond=0),
    }


def _build_access_response(application: dict) -> dict:
    application = _with_stale_status(application)
    schedule = _normalize_schedule(None, application)
    status = _get_schedule_access_status(application, schedule["scheduled_at"] if schedule else None)
    join_window_ends_at = _join_window_end(schedule["scheduled_at"]) if schedule else None
    response = {
        "success": True,
        "status": status["status"],
        "message": status["message"],
        "identityConfig": build_identity_config(application),
        "identity_config": build_identity_config(application),
        "interview_date": schedule["date"] if schedule else application.get("interview_date") or "",
        "interview_time": schedule["time"] if schedule else application.get("interview_time") or "",
        "interview_scheduled_at": schedule["scheduled_at"].isoformat() if schedule else application.get("interview_scheduled_at") or "",
        "scheduled_at": schedule["scheduled_at"].isoformat() if schedule else application.get("interview_scheduled_at") or "",
        "join_window_ends_at": join_window_ends_at.isoformat() if join_window_ends_at else application.get("join_window_ends_at"),
        "started_at": application.get("interview_started_at"),
        "completed_at": application.get("interview_completed_at") or application.get("completedAt"),
        "interview_session_id": application.get("interview_session_id"),
    }

    if schedule:
        response["scheduled_date_label"] = schedule["scheduled_at"].strftime("%Y-%m-%d")
        response["scheduled_time_label"] = schedule["scheduled_at"].strftime("%I:%M %p").lstrip("0")

    return response


def _attempt_access_error(application: dict, attempt: str | None) -> dict | None:
    active_attempt = str(application.get("active_attempt_id") or get_interview_link_token(application) or application.get("currentInterviewId") or "").strip()
    requested_attempt = str(attempt or "").strip()

    if requested_attempt:
        if active_attempt and requested_attempt != active_attempt:
            return {
                "success": True,
                "status": "expired",
                "message": "This interview link has expired. Please contact HR.",
            }

        return None

    return None


def _get_schedule_access_status(application: dict, scheduled_at: datetime | None) -> dict:
    if _is_interview_completed(application):
        return {
            "status": "complete",
            "message": "You have already completed this interview.",
        }

    current_status = _normalize_interview_status(application)

    if current_status == "partial":
        return {
            "status": current_status,
            "message": "Your previous interview attempt was interrupted. Please contact HR.",
        }

    if scheduled_at is None:
        return {
            "status": "missing_schedule",
            "message": "Set a proper interview date and time.",
        }

    now = _now_minute()
    join_window_ends_at = _join_window_end(scheduled_at)

    if now > join_window_ends_at:
        return {
            "status": "expired",
            "message": "This interview link has expired. Please contact HR.",
        }

    if scheduled_at > now:
        if scheduled_at.date() == now.date():
            return {
                "status": "too_early",
                "message": f"Your interview starts at {scheduled_at.strftime('%I:%M %p').lstrip('0')}. Please come back at the scheduled time.",
            }

        return {
            "status": "too_early",
            "message": (
                f"Your interview is scheduled for {scheduled_at.strftime('%Y-%m-%d')} "
                f"at {scheduled_at.strftime('%I:%M %p').lstrip('0')}. Please come back at the scheduled time."
            ),
        }

    return {
        "status": "allowed",
        "message": "Interview access allowed.",
    }


def _with_stale_status(application: dict) -> dict:
    if str(application.get("interview_status") or "").lower() not in {"in_progress"}:
        return application

    if _is_interview_completed(application):
        return application

    last_seen = _parse_datetime(application.get("interview_last_seen_at"))

    if not last_seen:
        return application

    if (datetime.now() - last_seen).total_seconds() <= HEARTBEAT_TIMEOUT_SECONDS:
        return application

    status = "partial" if _answered_count(application) > 0 else "not_started"
    application_id = application.get("application_id") or application.get("_id")

    if not application_id:
        return application

    finalized = finalize_partial_interview(str(application_id), status=status)
    return finalized or application


def _now_minute() -> datetime:
    return datetime.now().replace(second=0, microsecond=0)


def _join_window_end(scheduled_at: datetime) -> datetime:
    return scheduled_at + timedelta(minutes=JOIN_WINDOW_MINUTES)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    text = str(value).strip()

    if not text:
        return None

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)

    return parsed


def _normalize_liveness(value) -> dict:
    liveness = value if isinstance(value, dict) else {}
    events = liveness.get("events") if isinstance(liveness.get("events"), list) else []
    normalized = {
        "status": str(liveness.get("status") or "passed"),
        "total_warnings": int(liveness.get("total_warnings") or len(events) or 0),
        "no_face_count": int(liveness.get("no_face_count") or 0),
        "multiple_face_count": int(liveness.get("multiple_face_count") or 0),
        "identity_mismatch_count": int(liveness.get("identity_mismatch_count") or 0),
        "last_similarity": liveness.get("last_similarity"),
        "reference_set": liveness.get("reference_set") is True,
        "reference_embedding": liveness.get("reference_embedding"),
        "events": events,
    }
    normalized["status"] = _liveness_status(normalized["total_warnings"], normalized["identity_mismatch_count"])
    return normalized


def _normalize_liveness_event_type(value: str) -> str:
    event_type = str(value or "").strip().lower()
    return event_type if event_type in {"no_face_detected", "multiple_faces_detected", "identity_mismatch"} else ""


def _liveness_status(total_warnings: int, identity_mismatch_count: int = 0) -> str:
    if total_warnings >= 3 or identity_mismatch_count >= 2:
        return "suspicious"
    if total_warnings >= 1:
        return "warning"
    return "passed"


def _liveness_message(event_type: str) -> str:
    return {
        "no_face_detected": "Face not detected. Please stay visible on camera.",
        "multiple_faces_detected": "Multiple faces detected. Only the candidate should be visible.",
        "identity_mismatch": "Candidate identity mismatch detected. Please keep the same person on camera.",
    }.get(event_type, "Liveness warning detected.")


def _decode_base64_image(value: str) -> bytes:
    text = str(value or "").strip()

    if "," in text:
        text = text.split(",", 1)[1]

    try:
        return base64.b64decode(text, validate=True)
    except Exception:
        return b""


def _analyze_liveness_image(image: str) -> dict:
    result = analyze_face_image_bytes(_decode_base64_image(image))
    face_count = int(result.get("face_count") or 0)

    if result.get("success") and face_count == 1:
        return {
            "event_type": "face_match",
            "message": "Face detected",
            "embedding": result.get("embedding"),
            "similarity": None,
        }

    if face_count > 1:
        return {
            "event_type": "multiple_faces_detected",
            "message": "Multiple faces detected. Only the candidate should be visible.",
            "similarity": None,
        }

    return {
        "event_type": "no_face_detected",
        "message": "No face detected. Please stay visible on camera.",
        "similarity": None,
    }


def _analyze_liveness_images(payload: LivenessImageRequest) -> dict:
    images = [image for image in ([payload.image] + list(payload.images or [])) if str(image or "").strip()]

    if not images:
        return {
            "event_type": "no_face_detected",
            "message": "No face detected. Please stay visible on camera.",
            "similarity": None,
        }

    fallback = None

    for image in images[:3]:
        result = _analyze_liveness_image(image)

        if result["event_type"] == "face_match":
            return result

        if result["event_type"] == "multiple_faces_detected":
            fallback = result
        elif fallback is None:
            fallback = result

    return fallback or {
        "event_type": "no_face_detected",
        "message": "No face detected. Please stay visible on camera.",
        "similarity": None,
    }


def _record_liveness_result(
    application_id: str,
    application: dict,
    result: dict,
    payload: LivenessImageRequest | LivenessEventRequest,
) -> dict:
    liveness = _normalize_liveness(application.get("liveness"))
    event_type = result.get("event_type") or _normalize_liveness_event_type(getattr(payload, "type", ""))
    event = {
        "type": event_type,
        "timestamp": datetime.now().isoformat(),
        "question_index": getattr(payload, "question_index", None),
        "check_type": getattr(payload, "check_type", "") or "",
        "similarity": result.get("similarity"),
        "message": result.get("message") or _liveness_message(event_type),
    }
    liveness["events"].append(event)
    liveness["total_warnings"] = len(liveness["events"])

    if event_type == "no_face_detected":
        liveness["no_face_count"] += 1
    elif event_type == "multiple_faces_detected":
        liveness["multiple_face_count"] += 1
    elif event_type == "identity_mismatch":
        liveness["identity_mismatch_count"] += 1

    if result.get("similarity") is not None:
        liveness["last_similarity"] = result.get("similarity")

    liveness["status"] = _liveness_status(liveness["total_warnings"], liveness["identity_mismatch_count"])
    update_application(application_id, {"liveness": liveness})
    return liveness


def _liveness_response(ok: bool, status: str, event_type: str, similarity, message: str, liveness: dict) -> dict:
    return {
        "ok": ok,
        "success": ok,
        "status": status,
        "event_type": event_type,
        "similarity": similarity,
        "message": message,
        "liveness": _public_liveness(liveness),
    }


def _public_liveness(liveness: dict) -> dict:
    return {
        key: value
        for key, value in liveness.items()
        if key != "reference_embedding"
    }


def _embedding_to_list(embedding) -> list[float]:
    if embedding is None:
        return []

    if hasattr(embedding, "tolist"):
        return [float(value) for value in embedding.tolist()]

    return [float(value) for value in embedding]


def _upsert_saved_answer(application: dict, payload: AnswerSaveRequest) -> dict:
    interview_answers = application.get("interview_answers")

    if not isinstance(interview_answers, dict):
        interview_answers = {}

    question_id = payload.question_id or f"q{payload.question_index}"
    existing = interview_answers.get(question_id) if isinstance(interview_answers.get(question_id), dict) else {}
    now = datetime.now().isoformat()
    attempt_number = _current_attempt_number(application)
    answer = {
        **existing,
        "questionId": question_id,
        "question_id": question_id,
        "attemptNumber": attempt_number,
        "attempt_number": attempt_number,
        "archived": False,
        "question_index": payload.question_index,
        "question": payload.question or existing.get("question") or "",
        "expectedAnswer": payload.expected_answer or existing.get("expectedAnswer") or existing.get("expected_answer") or "",
        "expected_answer": payload.expected_answer or existing.get("expected_answer") or existing.get("expectedAnswer") or "",
        "answerText": payload.candidate_answer or existing.get("answerText") or existing.get("answer_text") or "",
        "answer_text": payload.candidate_answer or existing.get("answer_text") or existing.get("answerText") or "",
        "transcript": payload.candidate_answer or existing.get("transcript") or "",
        "candidate_answer": payload.candidate_answer or existing.get("candidate_answer") or "",
        "status": payload.status or existing.get("status") or "submitted",
        "answer_status": payload.status or existing.get("answer_status") or "submitted",
        "submittedAt": payload.submitted_at or existing.get("submittedAt") or now,
        "submitted_at": payload.submitted_at or existing.get("submitted_at") or now,
    }

    if payload.score is not None:
        answer["score"] = payload.score
        answer["finalScore"] = payload.score
        answer["final_score"] = payload.score

    if payload.feedback is not None:
        answer["feedback"] = payload.feedback

    interview_answers[question_id] = answer
    return {"interview_answers": interview_answers, "answer": answer}


def _answered_count(application: dict) -> int:
    answers = application.get("interview_answers")

    if not isinstance(answers, dict):
        return 0

    return len([
        answer
        for answer in answers.values()
        if isinstance(answer, dict)
        and answer.get("archived") is not True
        and str(answer.get("status") or answer.get("answer_status") or "").lower() != "unanswered"
        and str(answer.get("transcript") or answer.get("answerText") or answer.get("answer_text") or "").strip()
        and str(answer.get("transcript") or answer.get("answerText") or answer.get("answer_text") or "").strip().lower() != "not answered"
    ])


def _normalize_expiry_date(value: str | None) -> str:
    if value:
        parsed = datetime.fromisoformat(value)

        if len(value) <= 10:
            parsed = parsed.replace(hour=23, minute=59, second=59)

        return parsed.isoformat()

    return (datetime.now() + timedelta(days=7)).isoformat()


def _load_link_data(token: str) -> dict | None:
    return get_link_by_token(token)


def _mark_link_used(token: str) -> None:
    mark_link_used(token)


def _has_current_question_contract(question_payload: dict) -> bool:
    questions = question_payload.get("questions")

    if not isinstance(questions, list) or not questions:
        return False

    for index, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            return False

        if not question.get("question"):
            return False

        if str(question.get("id") or "") != f"q{index}":
            return False

        difficulty = str(question.get("difficulty") or "").lower()

        if difficulty not in {"easy", "medium", "hard"}:
            return False

    return True


def _get_candidate_name(application: dict) -> str:
    return (
        application.get("candidate_name")
        or _safe_get(application, ["resume", "candidate_name"])
        or application.get("resume_name")
        or application.get("file_name")
        or "Candidate"
    )
