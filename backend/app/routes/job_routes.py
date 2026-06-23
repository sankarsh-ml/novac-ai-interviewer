from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.db_service import (
    get_all_jobs,
    get_application_by_id,
    list_applications,
    save_job,
)
from app.services.json_storage_service import (
    cleanup_stale_empty_sessions,
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


def _total_score(answers: list[dict]) -> int | float:
    total = 0.0

    for answer in answers:
        try:
            total += float(answer.get("score", 0))
        except (TypeError, ValueError):
            continue

    return int(total) if total.is_integer() else round(total, 1)
