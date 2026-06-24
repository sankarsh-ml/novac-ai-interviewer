from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pathlib import Path
from pydantic import BaseModel

from app.services.db_service import (
    accept_application,
    delete_application,
    get_all_jobs,
    get_application_by_id,
    list_applications,
    save_job,
)
from app.services.mongo_interview_service import (
    get_candidate_by_application_id,
    hard_delete_candidate,
    list_interview_candidates,
    upsert_accepted_candidate,
)
from app.services.json_storage_service import (
    cleanup_stale_empty_sessions,
    delete_interview_session,
    get_interview_session,
    list_interview_sessions,
    submitted_answer_count,
    upsert_interview_session,
)


router = APIRouter()


class JobRequest(BaseModel):
    title: str
    required_skills: list[str]
    education: str
    experience: int
    keywords: list[str]


class AcceptApplicationRequest(BaseModel):
    frontend_base_url: str | None = None


@router.post("/jobs")
def create_job(job: JobRequest):
    job_id = save_job(
        {
            "title": job.title,
            "required_skills": job.required_skills,
            "education": job.education,
            "experience": job.experience,
            "keywords": job.keywords,
        }
    )

    return {
        "success": True,
        "job_id": job_id,
        "message": "Job created successfully",
    }


@router.get("/jobs")
def fetch_jobs():
    return {
        "success": True,
        "jobs": get_all_jobs(),
    }


@router.get("/applications")
def fetch_applications():
    return {
        "success": True,
        "applications": list_applications(),
    }


@router.get("/applications/{application_id}")
def fetch_application(application_id: str):
    application = get_application_by_id(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    return {
        "success": True,
        "application": application,
    }


@router.post("/applications/{application_id}/accept")
def accept_resume_application(
    application_id: str,
    request: AcceptApplicationRequest | None = None,
    force_regenerate: bool = False,
    frontend_base_url: str | None = None,
):
    try:
        application = accept_application(
            application_id,
            frontend_base_url=(
                (request.frontend_base_url if request else None)
                or frontend_base_url
            ),
            force_regenerate=force_regenerate,
        )
    except ValueError as error:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": str(error),
            },
        )

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    upsert_accepted_candidate(application)

    return {
        "success": True,
        "application_id": application.get("application_id"),
        "invite_token": application.get("invite_token"),
        "invite_link": application.get("invite_link"),
    }


@router.get("/interview-candidates")
def fetch_interview_candidates():
    return {
        "success": True,
        "candidates": list_interview_candidates(),
    }


@router.delete("/interview-candidates/{application_id}")
def delete_interview_candidate(application_id: str):
    candidate = get_candidate_by_application_id(application_id, include_deleted=True)
    application = get_application_by_id(application_id)

    if not candidate and not application:
        raise HTTPException(status_code=404, detail="Interview candidate not found")

    file_result = _delete_candidate_files(candidate or {}, application or {})
    deleted_mongo = hard_delete_candidate(application_id)
    deleted_application = delete_application(application_id)
    deleted_session = delete_interview_session(application_id)

    return {
        "success": True,
        "application_id": application_id,
        "deleted_mongo": deleted_mongo,
        "deleted_local_json": deleted_application or deleted_session,
        **file_result,
    }


@router.get("/interview/{session_id}/results")
def fetch_interview_results(session_id: str):
    cleanup_stale_empty_sessions()
    session = get_interview_session(session_id)

    if isinstance(session, dict):
        return {
            "success": True,
            **_result_from_session(session),
        }

    application = get_application_by_id(session_id)

    if not application:
        raise HTTPException(status_code=404, detail="Interview session not found")

    session = application.get("interview_session")

    if not isinstance(session, dict):
        session = _legacy_session_from_application(application)

    answers = session.get("answers") if isinstance(session.get("answers"), list) else []
    questions = session.get("questions") if isinstance(session.get("questions"), list) else []
    submitted_answers = _submitted_answers(answers)
    total_score = _total_score(submitted_answers)
    max_score = session.get("max_score") or len(questions) * 10
    status = _interview_status(session, questions, submitted_answers)

    return {
        "success": True,
        "candidate_info": session.get("candidate_info") or _candidate_info(application),
        "session_id": session.get("session_id") or session_id,
        "candidate_id": session.get("candidate_id") or session_id,
        "status": status,
        "total_score": total_score,
        "max_score": max_score,
        "questions": _merge_questions_and_answers(questions, answers),
    }


@router.get("/interviews/results")
def fetch_all_interview_results():
    sessions = list_interview_sessions(include_stale_cleanup=True)
    visible_sessions = [
        session
        for session in sessions
        if _should_show_session(session)
    ]

    return {
        "success": True,
        "results": [_result_from_session(session) for session in visible_sessions],
    }


def _result_from_session(session: dict) -> dict:
    questions = session.get("questions") if isinstance(session.get("questions"), list) else []
    submitted_questions = _submitted_questions(questions)
    status = _session_status(session, questions, submitted_questions)

    if status != session.get("status"):
        session["status"] = status

        if status == "completed" and not session.get("completed_at"):
            from datetime import datetime, timezone
            session["completed_at"] = datetime.now(timezone.utc).isoformat()

        upsert_interview_session(session)

    return {
        "candidate_info": session.get("candidate_info") or {
            "application_id": session.get("candidate_id"),
            "candidate_name": session.get("candidate_name") or "Candidate",
            "file_name": session.get("resume_file"),
        },
        "session_id": session.get("session_id"),
        "candidate_id": session.get("candidate_id"),
        "status": status,
        "total_score": _total_score(submitted_questions),
        "max_score": session.get("max_score") or 50,
        "questions": _merge_session_questions(questions),
        "submitted_answer_count": len(submitted_questions),
    }


def _should_show_session(session: dict) -> bool:
    questions = session.get("questions") if isinstance(session.get("questions"), list) else []
    submitted_questions = _submitted_questions(questions)
    status = _session_status(session, questions, submitted_questions)
    return status == "completed"


def _legacy_session_from_application(application: dict) -> dict:
    question_payload = application.get("interview_questions")
    questions = question_payload.get("questions") if isinstance(question_payload, dict) else []
    answers = _answers_dict_to_list(application.get("interview_answers"))

    submitted_answers = _submitted_answers(answers)

    return {
        "session_id": application.get("application_id"),
        "candidate_id": application.get("application_id"),
        "candidate_info": _candidate_info(application),
        "status": _interview_status({"status": application.get("interview_status")}, questions, submitted_answers),
        "total_score": _total_score(submitted_answers),
        "max_score": len(questions) * 10,
        "questions": _merge_questions_and_answers(questions, answers),
        "answers": answers,
    }


def _merge_questions_and_answers(questions: list, answers: list[dict]) -> list[dict]:
    answers_by_question = {
        str(answer.get("question_id")): answer
        for answer in answers
        if isinstance(answer, dict)
    }

    rows = []

    for question in questions:
        if not isinstance(question, dict):
            continue

        answer = answers_by_question.get(str(question.get("id")), {})
        rows.append(
            {
                "question_id": question.get("id"),
                "question_text": question.get("question"),
                "category": question.get("category"),
                "difficulty": question.get("difficulty"),
                "score": answer.get("score"),
                "feedback": answer.get("feedback"),
                "transcript": answer.get("transcript"),
                "transcript_file_path": answer.get("transcript_file_path"),
                "audio_file_path": answer.get("audio_file_path"),
                "submitted_at": answer.get("submitted_at"),
                "evaluation": answer.get("evaluation"),
            }
        )

    return rows


def _merge_session_questions(questions: list) -> list[dict]:
    rows = []

    for question in questions:
        if not isinstance(question, dict):
            continue

        rows.append(
            {
                "question_id": question.get("question_id"),
                "question_text": question.get("question_text"),
                "category": question.get("category"),
                "difficulty": question.get("difficulty"),
                "score": question.get("score"),
                "feedback": question.get("feedback"),
                "transcript": question.get("transcript"),
                "transcript_file_path": question.get("transcript_file_path"),
                "audio_file_path": question.get("audio_file_path"),
                "submitted_at": question.get("submitted_at"),
                "evaluation": question.get("evaluation"),
            }
        )

    return rows


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


def _submitted_questions(questions: list[dict]) -> list[dict]:
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


def _session_status(session: dict, questions: list, submitted_questions: list[dict]) -> str:
    if len(questions) == 5 and len(submitted_questions) == 5:
        return "completed"

    if session.get("status") in {"abandoned", "incomplete"} and submitted_questions:
        return session.get("status")

    if submitted_questions:
        return "in_progress"

    return session.get("status") or "not_started"


def _interview_status(session: dict, questions: list, submitted_answers: list[dict]) -> str:
    if session.get("status") == "completed":
        return "completed"

    if len(questions) == 5 and len(submitted_answers) >= 5:
        return "completed"

    if submitted_answers:
        return "in_progress"

    return session.get("status") or "not_started"


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


def _safe_get(mapping: dict, keys: list[str]):
    current = mapping

    for key in keys:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def _delete_candidate_files(candidate: dict, application: dict) -> dict:
    deleted_files = []
    missing_files = []
    skipped_files = []

    for raw_path in _candidate_file_paths(candidate, application):
        file_path = _resolve_project_file(raw_path)

        if not file_path:
            skipped_files.append(str(raw_path))
            continue

        try:
            if file_path.is_file():
                file_path.unlink()
                deleted_files.append(str(file_path))
            else:
                missing_files.append(str(file_path))
        except OSError:
            skipped_files.append(str(file_path))

    deleted_folders = _prune_empty_candidate_dirs(deleted_files)

    return {
        "deleted_files": deleted_files,
        "deleted_folders": deleted_folders,
        "missing_files": missing_files,
        "skipped_files": skipped_files,
    }


def _candidate_file_paths(candidate: dict, application: dict) -> list[str]:
    paths = [
        application.get("file_path"),
        application.get("resume_photo_path"),
        _safe_get(application, ["resume", "resume_photo_path"]),
        application.get("aadhaar_photo_path"),
        _safe_get(application, ["kyc", "aadhaar_photo_path"]),
        _safe_get(application, ["kyc_verification", "aadhaar_photo_path"]),
        _safe_get(application, ["aadhaar_verification", "aadhaar_photo_path"]),
        _safe_get(application, ["interview_session", "face_verification", "live_frame_path"]),
    ]

    for question in candidate.get("questions") or []:
        if isinstance(question, dict):
            paths.extend([
                question.get("audio_file_path"),
                question.get("transcript_file_path"),
            ])

    session = application.get("interview_session") if isinstance(application.get("interview_session"), dict) else {}

    for collection_name in ("questions", "answers"):
        for item in session.get(collection_name) or []:
            if isinstance(item, dict):
                paths.extend([
                    item.get("audio_file_path"),
                    item.get("transcript_file_path"),
                ])

    unique_paths = []
    seen = set()

    for path in paths:
        if not path:
            continue

        normalized = str(path)
        if normalized in seen:
            continue

        seen.add(normalized)
        unique_paths.append(normalized)

    return unique_paths


def _resolve_project_file(raw_path: str) -> Path | None:
    project_root = Path(__file__).resolve().parents[3]
    path = Path(str(raw_path))

    if not path.is_absolute():
        path = project_root / path

    try:
        resolved = path.resolve()
    except OSError:
        return None

    if not _is_relative_to(resolved, project_root):
        return None

    return resolved


def _prune_empty_candidate_dirs(deleted_files: list[str]) -> list[str]:
    project_root = Path(__file__).resolve().parents[3]
    allowed_roots = [
        project_root / "backend" / "uploads",
        project_root / "backend" / "app" / "storage",
    ]
    deleted_folders = []

    for deleted_file in deleted_files:
        folder = Path(deleted_file).parent

        while any(_is_relative_to(folder, root.resolve()) and folder != root.resolve() for root in allowed_roots):
            try:
                folder.rmdir()
                deleted_folders.append(str(folder))
            except OSError:
                break

            folder = folder.parent

    return deleted_folders


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _total_score(answers: list[dict]) -> int | float:
    total = 0.0

    for answer in answers:
        try:
            total += float(answer.get("score", 0))
        except (TypeError, ValueError):
            continue

    return int(total) if total.is_integer() else round(total, 1)
