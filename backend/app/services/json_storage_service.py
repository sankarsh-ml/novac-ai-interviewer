from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import threading


BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"
INTERVIEW_SESSIONS_FILE = DATA_DIR / "interview_sessions.json"
_LOCK = threading.Lock()


def list_interview_sessions(include_stale_cleanup: bool = False) -> list[dict]:
    if include_stale_cleanup:
        cleanup_stale_empty_sessions()

    with _LOCK:
        return _load_json_list(INTERVIEW_SESSIONS_FILE)


def get_interview_session(session_id: str) -> dict | None:
    if not session_id:
        return None

    for session in list_interview_sessions():
        if str(session.get("session_id")) == str(session_id):
            return session

    return None


def upsert_interview_session(session: dict) -> dict:
    session_id = str(session.get("session_id") or "").strip()

    if not session_id:
        raise ValueError("session_id is required")

    safe_session = _json_safe(session)

    with _LOCK:
        sessions = _load_json_list(INTERVIEW_SESSIONS_FILE)

        for index, existing in enumerate(sessions):
            if str(existing.get("session_id")) == session_id:
                sessions[index] = safe_session
                _save_json_list(INTERVIEW_SESSIONS_FILE, sessions)
                return safe_session

        sessions.append(safe_session)
        _save_json_list(INTERVIEW_SESSIONS_FILE, sessions)
        return safe_session


def update_interview_session(session_id: str, updates: dict) -> dict | None:
    session = get_interview_session(session_id)

    if not session:
        return None

    session.update(_json_safe(updates))
    return upsert_interview_session(session)


def delete_interview_session(session_id: str) -> bool:
    with _LOCK:
        sessions = _load_json_list(INTERVIEW_SESSIONS_FILE)
        kept_sessions = [
            session
            for session in sessions
            if str(session.get("session_id")) != str(session_id)
        ]

        if len(kept_sessions) == len(sessions):
            return False

        _save_json_list(INTERVIEW_SESSIONS_FILE, kept_sessions)
        return True


def cleanup_stale_empty_sessions(minutes: int = 30) -> list[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    deleted_session_ids = []

    with _LOCK:
        sessions = _load_json_list(INTERVIEW_SESSIONS_FILE)
        kept_sessions = []

        for session in sessions:
            if _is_stale_empty_in_progress(session, cutoff):
                deleted_session_ids.append(str(session.get("session_id")))
                continue

            kept_sessions.append(session)

        if len(kept_sessions) != len(sessions):
            _save_json_list(INTERVIEW_SESSIONS_FILE, kept_sessions)

    return deleted_session_ids


def submitted_answer_count(session: dict) -> int:
    return len(
        [
            question
            for question in session.get("questions", [])
            if isinstance(question, dict)
            and (
                question.get("submitted_at")
                or question.get("transcript")
                or question.get("score") is not None
            )
        ]
    )


def _is_stale_empty_in_progress(session: dict, cutoff: datetime) -> bool:
    if session.get("status") != "in_progress":
        return False

    if submitted_answer_count(session) > 0:
        return False

    created_at = _parse_datetime(session.get("created_at"))
    return bool(created_at and created_at < cutoff)


def _load_json_list(file_path: Path) -> list[dict]:
    _ensure_data_file(file_path)

    try:
        text = file_path.read_text(encoding="utf-8").strip()
    except OSError:
        return []

    if not text:
        return []

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        backup_path = file_path.with_suffix(f".corrupt-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.json")
        try:
            file_path.replace(backup_path)
        except OSError:
            pass
        _ensure_data_file(file_path)
        return []

    return data if isinstance(data, list) else []


def _save_json_list(file_path: Path, data: list[dict]) -> None:
    _ensure_data_file(file_path)
    file_path.write_text(json.dumps(_json_safe(data), indent=2), encoding="utf-8")


def _ensure_data_file(file_path: Path) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not file_path.exists():
        file_path.write_text("[]\n", encoding="utf-8")


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _json_safe(value):
    return json.loads(json.dumps(value, default=str))


_ensure_data_file(INTERVIEW_SESSIONS_FILE)
