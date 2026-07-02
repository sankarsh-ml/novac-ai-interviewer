from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.application.services.admin_service import _bearer_token, bearer_scheme, create_access_token, decode_access_token
from app.application.services.application_store_service import get_resume_application
from app.application.services.identity_config_service import build_identity_config
from app.application.services.interview_service import get_link_by_token
from app.repositories.job_repository import get_by_id as get_job_by_id
from app.utils.interview_tokens import get_interview_link_token


def issue_candidate_token(interview_link_token: str) -> dict:
    token = str(interview_link_token or "").strip()

    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Interview link token is required")

    interview = get_link_by_token(token)

    if not interview:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview link not found")

    candidate_id = _candidate_id(interview)
    interview_id = _interview_id(interview)

    if not candidate_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found for this interview link")

    application = get_resume_application(candidate_id)

    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found for this interview link")

    job_id = _job_id(interview, application)

    if job_id and not get_job_by_id(str(job_id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found for this interview link")

    active_token = get_interview_link_token(interview) or get_interview_link_token(application)

    if active_token and active_token != token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Interview link token mismatch")

    if _is_interview_completed(application) or interview.get("used"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Interview already completed")

    _ensure_link_not_expired(interview)
    expires_delta = timedelta(minutes=_candidate_jwt_expire_minutes())
    access_token = create_access_token(
        {
            "sub": candidate_id,
            "role": "candidate",
            "candidateId": candidate_id,
            "jobId": str(job_id or ""),
            "interviewId": interview_id,
            "interviewLinkToken": token,
        },
        expires_delta=expires_delta,
    )

    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "candidate": {
            "candidateId": candidate_id,
            "jobId": str(job_id or ""),
            "interviewId": interview_id,
        },
        "identityConfig": build_identity_config(application),
        "identity_config": build_identity_config(application),
    }


def require_candidate_jwt(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict:
    token = _bearer_token(credentials, "Invalid or expired candidate token")
    payload = decode_access_token(token, detail="Invalid or expired candidate token")

    if payload.get("role") != "candidate":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Candidate token required")

    candidate_id = str(payload.get("candidateId") or payload.get("sub") or "").strip()
    interview_id = str(payload.get("interviewId") or "").strip()
    interview_link_token = str(payload.get("interviewLinkToken") or "").strip()

    if not candidate_id or not interview_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired candidate token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    application = get_resume_application(candidate_id)

    if not application:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired candidate token")

    stored_interview_id = str(
        application.get("interviewId")
        or application.get("interview_id")
        or get_interview_link_token(application)
        or ""
    ).strip()

    if stored_interview_id and stored_interview_id != interview_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired candidate token")

    stored_token = get_interview_link_token(application)

    if interview_link_token and stored_token and interview_link_token != stored_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired candidate token")

    if _is_interview_completed(application):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Interview already completed")

    return {
        **payload,
        "candidateId": candidate_id,
        "jobId": str(payload.get("jobId") or application.get("jobId") or application.get("job_id") or ""),
        "interviewId": interview_id,
        "interviewLinkToken": interview_link_token,
        "application": application,
    }


def require_admin_or_candidate_jwt(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict:
    token = _bearer_token(credentials)
    payload = decode_access_token(token)
    role = payload.get("role")

    if role not in {"admin", "candidate"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin or candidate token required")

    return payload


def assert_candidate_application(application_id: str, current_candidate: dict) -> str:
    candidate_id = str(current_candidate.get("candidateId") or "").strip()

    if not candidate_id or str(application_id or "").strip() != candidate_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Candidate token does not match this candidate")

    return candidate_id


def _candidate_id(interview: dict) -> str:
    return str(interview.get("candidateId") or interview.get("candidate_id") or interview.get("application_id") or "").strip()


def _interview_id(interview: dict) -> str:
    return str(
        interview.get("interviewId")
        or interview.get("interview_id")
        or get_interview_link_token(interview)
        or ""
    ).strip()


def _job_id(interview: dict, application: dict) -> str:
    return str(
        interview.get("jobId")
        or interview.get("job_id")
        or application.get("jobId")
        or application.get("job_id")
        or ""
    ).strip()


def _ensure_link_not_expired(interview: dict) -> None:
    expiry = _parse_datetime(interview.get("expiry_date") or interview.get("expiresAt") or interview.get("expires_at"))

    if expiry and datetime.now(expiry.tzinfo or timezone.utc) > expiry:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Interview link expired")


def _parse_datetime(value) -> datetime | None:
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

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed


def _candidate_jwt_expire_minutes() -> int:
    try:
        return int(os.getenv("CANDIDATE_JWT_EXPIRE_MINUTES", "240"))
    except (TypeError, ValueError):
        return 240


def _is_interview_completed(application: dict) -> bool:
    status = str(application.get("interview_status") or application.get("interviewStatus") or "").lower()
    report_status = str(application.get("report_status") or "").lower()

    return (
        application.get("interview_completed") is True
        or application.get("interviewCompleted") is True
        or bool(application.get("interview_completed_at") or application.get("completedAt") or application.get("completed_at"))
        or status in {"complete", "completed"}
        or report_status in {"complete", "completed"}
        or application.get("completed_report_generated") is True
        or application.get("completedReportGenerated") is True
    )
