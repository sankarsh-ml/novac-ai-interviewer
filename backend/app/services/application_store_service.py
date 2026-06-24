from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import threading
import uuid


APP_DIR = Path(__file__).resolve().parents[1]
STORAGE_DIR = APP_DIR / "storage"
APPLICATIONS_FILE = STORAGE_DIR / "applications.json"
JOBS_FILE = STORAGE_DIR / "jobs.json"

_STORE_LOCK = threading.Lock()


def create_application(data: dict) -> str:
    now = _now()
    application = {
        "application_id": data.get("application_id") or str(uuid.uuid4()),
        **_json_safe(data),
        "created_at": data.get("created_at") or now,
        "updated_at": data.get("updated_at") or now,
    }

    with _STORE_LOCK:
        applications = _load_json(APPLICATIONS_FILE)
        applications.append(application)
        _save_json(APPLICATIONS_FILE, applications)

    return application["application_id"]


def get_application_by_id(application_id: str) -> dict | None:
    if not application_id:
        return None

    for application in list_applications():
        if _matches_application_id(application, application_id):
            return application

    return None


def update_application(application_id: str, updates: dict) -> bool:
    if not application_id:
        return False

    with _STORE_LOCK:
        applications = _load_json(APPLICATIONS_FILE)

        for index, application in enumerate(applications):
            if _matches_application_id(application, application_id):
                updated_application = {
                    **application,
                    **_json_safe(updates),
                    "updated_at": _now(),
                }
                applications[index] = updated_application
                _save_json(APPLICATIONS_FILE, applications)
                return True

    return False


def delete_application(application_id: str) -> bool:
    if not application_id:
        return False

    with _STORE_LOCK:
        applications = _load_json(APPLICATIONS_FILE)
        kept_applications = [
            application
            for application in applications
            if not _matches_application_id(application, application_id)
        ]

        if len(kept_applications) == len(applications):
            return False

        _save_json(APPLICATIONS_FILE, kept_applications)
        return True


def accept_application(
    application_id: str,
    frontend_base_url: str | None = None,
    force_regenerate: bool = False,
) -> dict | None:
    if not application_id:
        return None

    base_url = (frontend_base_url or os.getenv("FRONTEND_BASE_URL") or "http://127.0.0.1:5174").rstrip("/")

    with _STORE_LOCK:
        applications = _load_json(APPLICATIONS_FILE)
        existing_tokens = {
            str(application.get("invite_token"))
            for application in applications
            if application.get("invite_token")
        }

        for index, application in enumerate(applications):
            if not _matches_application_id(application, application_id):
                continue

            ats_score = _application_ats_score(application)

            if ats_score is None:
                raise ValueError("ATS score not found. Run ATS before accepting resume.")

            if ats_score < 65:
                raise ValueError("ATS score below 65. Cannot generate interview link.")

            invite_token = (
                _generate_unique_invite_token(existing_tokens)
                if force_regenerate or not application.get("invite_token")
                else application.get("invite_token")
            )
            invite_link = f"{base_url}/candidate/invite/{invite_token}"
            now = _now()
            updated_application = {
                **application,
                "status": "accepted",
                "ats_score": ats_score,
                "ats_status": "passed",
                "ats_decision": "passed",
                "accepted_at": application.get("accepted_at") or now,
                "invite_token": invite_token,
                "invite_link": invite_link,
                "aadhaar_verified": (
                    application.get("aadhaar_verified")
                    if "aadhaar_verified" in application
                    else False
                ),
                "face_verified": (
                    application.get("face_verified")
                    if "face_verified" in application
                    else False
                ),
                "interview_status": application.get("interview_status") or "not_started",
                "updated_at": now,
            }
            updated_application = {
                **updated_application,
                "candidate_status": _candidate_status(updated_application),
            }
            applications[index] = _json_safe(updated_application)
            _save_json(APPLICATIONS_FILE, applications)
            return updated_application

    return None


def find_application_by_invite_token(token: str) -> dict | None:
    clean_token = str(token or "").strip()

    if not clean_token:
        return None

    for application in list_applications():
        if str(application.get("invite_token") or "") == clean_token:
            return application

    return None


def update_candidate_step(application_id: str, updates: dict) -> bool:
    if not application_id:
        return False

    next_updates = {**_json_safe(updates)}
    application = get_application_by_id(application_id) or {}
    merged_application = {**application, **next_updates}
    next_updates["candidate_status"] = _candidate_status(merged_application)

    return update_application(application_id, next_updates)


def candidate_invite_state(application: dict) -> dict:
    aadhaar_verified = _is_aadhaar_verified(application)
    face_verified = _is_face_verified(application)
    interview_status = _interview_status(application)
    next_step = _candidate_next_step(
        aadhaar_verified=aadhaar_verified,
        face_verified=face_verified,
        interview_status=interview_status,
    )

    return {
        "application_id": application.get("application_id") or application.get("_id"),
        "candidate_name": _candidate_name(application),
        "resume_file": application.get("file_name") or application.get("saved_file_name"),
        "ats_score": application.get("ats_score") or _safe_get(application, ["ats_result", "ats_score"]),
        "ats_status": application.get("ats_status") or _safe_get(application, ["ats_result", "ats_status"]),
        "status": application.get("status") or "accepted",
        "candidate_status": _candidate_status(application),
        "aadhaar_verified": aadhaar_verified,
        "face_verified": face_verified,
        "interview_status": interview_status,
        "next_step": next_step,
    }


def list_applications() -> list[dict]:
    with _STORE_LOCK:
        return _load_json(APPLICATIONS_FILE)


def update_ats_decision(application_id: str, decision: str) -> bool:
    normalized_decision = str(decision or "").lower().strip()
    return update_application(
        application_id,
        {
            "ats_status": normalized_decision,
            "ats_decision": normalized_decision,
        },
    )


def update_kyc_verification(application_id: str, data: dict) -> bool:
    updates = {
        "aadhaar_verification": data,
        "kyc_verification": data,
    }

    if isinstance(data, dict) and data.get("verification_status") == "passed":
        updates.update(
            {
                "aadhaar_verified": True,
                "aadhaar_verified_at": data.get("updated_at") or _now(),
                "status": "aadhaar_verified",
            }
        )

    aadhaar_photo_path = data.get("aadhaar_photo_path") if isinstance(data, dict) else None
    if aadhaar_photo_path:
        updates["aadhaar_photo_path"] = aadhaar_photo_path

    return update_candidate_step(application_id, updates)


def update_interview_status(application_id: str, data: dict) -> bool:
    return update_candidate_step(application_id, {"interview_status": data})


def save_job(job_data: dict) -> str:
    job = {
        "id": job_data.get("id") or str(uuid.uuid4()),
        **_json_safe(job_data),
    }

    with _STORE_LOCK:
        jobs = _load_json(JOBS_FILE)
        jobs.append(job)
        _save_json(JOBS_FILE, jobs)

    return job["id"]


def get_all_jobs() -> list[dict]:
    with _STORE_LOCK:
        return _load_json(JOBS_FILE)


def get_job_by_id(job_id: str) -> dict | None:
    if not job_id:
        return None

    for job in get_all_jobs():
        if str(job.get("id")) == str(job_id):
            return job

    return None


def clear_old_application_records(clear_applications: bool = False) -> dict:
    with _STORE_LOCK:
        applications = _load_json(APPLICATIONS_FILE)

        if clear_applications:
            _save_json(APPLICATIONS_FILE, [])
            return {
                "applications_seen": len(applications),
                "applications_cleared": len(applications),
                "applications_updated": 0,
            }

        kept_applications = [
            application
            for application in applications
            if not _is_stale_invite_or_interview_record(application)
        ]
        cleared_count = len(applications) - len(kept_applications)

        _save_json(APPLICATIONS_FILE, kept_applications)

    return {
        "applications_seen": len(applications),
        "applications_cleared": cleared_count,
        "applications_updated": 0,
    }


def _ensure_store_files():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    for folder_name in (
        "resumes",
        "aadhaar",
        "aadhaar_photos",
        "resume_photos",
        "live_frames",
    ):
        (STORAGE_DIR / folder_name).mkdir(parents=True, exist_ok=True)

    for file_path in (APPLICATIONS_FILE, JOBS_FILE):
        if not file_path.exists():
            _save_json(file_path, [])


def _load_json(file_path: Path) -> list[dict]:
    _ensure_store_files_without_recursing()

    if not file_path.exists():
        return []

    try:
        with file_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError:
        return []

    return data if isinstance(data, list) else []


def _save_json(file_path: Path, data: list[dict]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("w", encoding="utf-8") as file:
        json.dump(_json_safe(data), file, indent=2)


def _ensure_store_files_without_recursing():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    for folder_name in (
        "resumes",
        "aadhaar",
        "aadhaar_photos",
        "resume_photos",
        "live_frames",
    ):
        (STORAGE_DIR / folder_name).mkdir(parents=True, exist_ok=True)

    for file_path in (APPLICATIONS_FILE, JOBS_FILE):
        if not file_path.exists():
            file_path.write_text("[]\n", encoding="utf-8")


def _matches_application_id(application: dict, application_id: str) -> bool:
    return str(application.get("application_id") or application.get("_id") or "") == str(application_id)


def _generate_unique_invite_token(existing_tokens: set[str]) -> str:
    while True:
        token = secrets.token_urlsafe(24)

        if token not in existing_tokens:
            return token


def _candidate_name(application: dict) -> str:
    return (
        application.get("candidate_name")
        or _safe_get(application, ["resume", "candidate_name"])
        or application.get("file_name")
        or "Candidate"
    )


def _application_ats_score(application: dict) -> float | None:
    candidates = [
        application.get("ats_score"),
        _safe_get(application, ["ats_result", "ats_score"]),
        application.get("score"),
        application.get("atsScore"),
        application.get("match_score"),
        application.get("percentage"),
    ]

    for value in candidates:
        if value is None:
            continue

        try:
            return float(value)
        except (TypeError, ValueError):
            continue

    return None


def _is_aadhaar_verified(application: dict) -> bool:
    if "aadhaar_verified" in application:
        return application.get("aadhaar_verified") is True

    verification = application.get("aadhaar_verification")
    fallback_verification = application.get("kyc_verification")

    return bool(
        application.get("aadhaar_verified")
        or (isinstance(verification, dict) and verification.get("verification_status") == "passed")
        or (isinstance(verification, dict) and verification.get("name_match_passed") is True)
        or (
            isinstance(fallback_verification, dict)
            and fallback_verification.get("verification_status") == "passed"
        )
        or (
            isinstance(fallback_verification, dict)
            and fallback_verification.get("name_match_passed") is True
        )
    )


def _is_face_verified(application: dict) -> bool:
    if "face_verified" in application:
        return application.get("face_verified") is True

    session = application.get("interview_session")

    return bool(
        isinstance(session, dict) and session.get("face_verified")
    )


def _interview_status(application: dict) -> str:
    session = application.get("interview_session")
    status = application.get("interview_status")

    if status:
        return str(status)

    if isinstance(session, dict) and session.get("status"):
        if session.get("status") == "in_progress" and not _has_submitted_answers(session):
            return "not_started"

        return str(session.get("status"))

    return "not_started"


def _candidate_next_step(*, aadhaar_verified: bool, face_verified: bool, interview_status: str) -> str:
    if not aadhaar_verified:
        return "aadhaar"

    if not face_verified:
        return "face"

    if str(interview_status or "").lower() == "completed":
        return "completed"

    return "interview"


def _candidate_status(application: dict) -> str:
    aadhaar_verified = _is_aadhaar_verified(application)
    face_verified = _is_face_verified(application)
    interview_status = _interview_status(application).lower()

    if interview_status == "completed":
        return "completed"

    if interview_status == "in_progress":
        return "interview_in_progress"

    if face_verified:
        return "face_verified"

    if aadhaar_verified:
        return "aadhaar_verified"

    if application.get("invite_token") or application.get("status") == "accepted":
        return "invited"

    return application.get("status") or application.get("ats_status") or "pending"


def _is_stale_invite_or_interview_record(application: dict) -> bool:
    if application.get("invite_token") or application.get("invite_link"):
        return True

    if application.get("candidate_status"):
        return True

    if application.get("interview_session") or application.get("interview_answers"):
        return True

    if application.get("interview_status") and application.get("interview_status") != "not_started":
        return True

    return application.get("status") in {
        "accepted",
        "invited",
        "aadhaar_verified",
        "face_verified",
        "interview_in_progress",
        "interview_completed",
    }


def _has_submitted_answers(session: dict) -> bool:
    questions = session.get("questions") if isinstance(session, dict) else []

    if not isinstance(questions, list):
        return False

    return any(
        isinstance(question, dict)
        and (
            question.get("submitted_at")
            or question.get("transcript")
            or question.get("score") is not None
        )
        for question in questions
    )


def _safe_get(mapping: dict, keys: list[str]):
    current = mapping

    for key in keys:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def _json_safe(value):
    return json.loads(json.dumps(value, default=_json_default))


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()

    return str(value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_ensure_store_files()
