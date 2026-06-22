from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
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

    aadhaar_photo_path = data.get("aadhaar_photo_path") if isinstance(data, dict) else None
    if aadhaar_photo_path:
        updates["aadhaar_photo_path"] = aadhaar_photo_path

    return update_application(application_id, updates)


def update_interview_status(application_id: str, data: dict) -> bool:
    return update_application(application_id, {"interview_status": data})


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


def _json_safe(value):
    return json.loads(json.dumps(value, default=_json_default))


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()

    return str(value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_ensure_store_files()
