from __future__ import annotations

from datetime import datetime, timezone
import os

from bson import ObjectId
from pymongo import MongoClient, ReturnDocument


MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "ai_hiring_platform")
COLLECTION_NAME = "interview_candidates"
MAX_QUESTION_SCORE = 10

_CLIENT: MongoClient | None = None


def get_collection():
    global _CLIENT

    if _CLIENT is None:
        _CLIENT = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)

    return _CLIENT[MONGO_DB_NAME][COLLECTION_NAME]


def upsert_accepted_candidate(application: dict) -> dict:
    now = _now()
    application_id = str(application.get("application_id") or application.get("_id") or "")

    if not application_id:
        raise ValueError("application_id is required")

    existing = get_candidate_by_application_id(application_id, include_deleted=True) or {}
    invite_token = application.get("invite_token") or existing.get("invite_token")
    invite_link = application.get("invite_link") or existing.get("invite_link")
    questions = existing.get("questions") if isinstance(existing.get("questions"), list) else []

    document = {
        "application_id": application_id,
        "candidate_name": _candidate_name(application),
        "resume_file": application.get("file_name") or application.get("saved_file_name"),
        "ats_score": _number(application.get("ats_score") or _safe_get(application, ["ats_result", "ats_score"]), 0),
        "ats_status": application.get("ats_status") or "passed",
        "status": existing.get("status") or "invited",
        "invite_token": invite_token,
        "invite_link": invite_link,
        "aadhaar_verified": bool(existing.get("aadhaar_verified", application.get("aadhaar_verified", False))),
        "aadhaar_verified_at": existing.get("aadhaar_verified_at") or application.get("aadhaar_verified_at"),
        "face_verified": bool(existing.get("face_verified", application.get("face_verified", False))),
        "face_verified_at": existing.get("face_verified_at") or application.get("face_verified_at"),
        "interview_status": existing.get("interview_status") or application.get("interview_status") or "not_started",
        "total_score": _number(existing.get("total_score"), 0),
        "max_score": existing.get("max_score") or 50,
        "questions": questions,
        "accepted_at": existing.get("accepted_at") or application.get("accepted_at") or now,
        "completed_at": existing.get("completed_at"),
        "deleted": False,
        "deleted_at": None,
        "updated_at": now,
    }

    update = {
        "$set": document,
        "$setOnInsert": {
            "created_at": application.get("created_at") or now,
        },
    }

    saved = get_collection().find_one_and_update(
        {"application_id": application_id},
        update,
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return _serialize(saved)


def get_candidate_by_token(token: str) -> dict | None:
    if not token:
        return None

    document = get_collection().find_one({"invite_token": token, "deleted": {"$ne": True}})
    return _serialize(document) if document else None


def get_candidate_by_application_id(application_id: str, include_deleted: bool = False) -> dict | None:
    if not application_id:
        return None

    query = {"application_id": str(application_id)}
    if not include_deleted:
        query["deleted"] = {"$ne": True}

    document = get_collection().find_one(query)
    return _serialize(document) if document else None


def list_interview_candidates() -> list[dict]:
    cursor = get_collection().find({"deleted": {"$ne": True}}).sort(
        [("accepted_at", -1), ("created_at", -1), ("completed_at", -1)]
    )
    return [_serialize(document) for document in cursor]


def soft_delete_candidate(application_id: str) -> bool:
    result = get_collection().update_one(
        {"application_id": str(application_id), "deleted": {"$ne": True}},
        {
            "$set": {
                "deleted": True,
                "deleted_at": _now(),
                "updated_at": _now(),
            }
        },
    )
    return result.modified_count > 0


def hard_delete_candidate(application_id: str) -> bool:
    result = get_collection().delete_one({"application_id": str(application_id)})
    return result.deleted_count > 0


def clear_interview_candidates() -> int:
    result = get_collection().delete_many({})
    return result.deleted_count


def mark_aadhaar_verified(application_id: str) -> None:
    _update_candidate(
        application_id,
        {
            "aadhaar_verified": True,
            "aadhaar_verified_at": _now(),
            "status": "aadhaar_verified",
            "updated_at": _now(),
        },
    )


def mark_face_verified(application_id: str) -> None:
    _update_candidate(
        application_id,
        {
            "face_verified": True,
            "face_verified_at": _now(),
            "status": "face_verified",
            "updated_at": _now(),
        },
    )


def initialize_questions(application_id: str, question_payload: dict) -> None:
    questions = question_payload.get("questions") if isinstance(question_payload, dict) else []

    if not isinstance(questions, list):
        return

    candidate = get_candidate_by_application_id(application_id)
    existing_questions = candidate.get("questions") if isinstance(candidate, dict) else []

    if isinstance(existing_questions, list) and existing_questions:
        return

    initialized = [_question_document(question) for question in questions[:5]]
    _update_candidate(
        application_id,
        {
            "questions": initialized,
            "max_score": len(initialized) * MAX_QUESTION_SCORE,
            "interview_status": "not_started",
            "updated_at": _now(),
        },
    )


def update_question_answer(application_id: str, question_payload: dict, answer_record: dict) -> None:
    initialize_questions(application_id, question_payload)
    candidate = get_candidate_by_application_id(application_id)

    if not candidate:
        return

    question_id = str(answer_record.get("question_id") or "")
    questions = candidate.get("questions") if isinstance(candidate.get("questions"), list) else []
    updated_questions = []
    found = False

    for question in questions:
        if str(question.get("question_id")) == question_id:
            found = True
            updated_questions.append(
                {
                    **question,
                    "audio_file_path": answer_record.get("audio_file_path"),
                    "transcript_file_path": answer_record.get("transcript_file_path"),
                    "transcript": answer_record.get("transcript") or "",
                    "score": _number(answer_record.get("score"), 0),
                    "feedback": answer_record.get("feedback") or "",
                    "evaluation": answer_record.get("evaluation") or {},
                    "submitted_at": answer_record.get("submitted_at") or _now(),
                    "answered": True,
                }
            )
        else:
            updated_questions.append(question)

    if not found:
        updated_questions.append(_answer_to_question_document(answer_record))

    total_score = _total_score(updated_questions)
    _update_candidate(
        application_id,
        {
            "questions": updated_questions,
            "total_score": total_score,
            "max_score": max(len(updated_questions), 5) * MAX_QUESTION_SCORE,
            "interview_status": "in_progress",
            "status": "interview_in_progress",
            "updated_at": _now(),
        },
    )


def complete_interview_candidate(application_id: str) -> None:
    candidate = get_candidate_by_application_id(application_id)

    if not candidate:
        return

    questions = _five_questions(candidate.get("questions"))
    total_score = _total_score(questions)
    _update_candidate(
        application_id,
        {
            "questions": questions,
            "total_score": total_score,
            "max_score": 50,
            "interview_status": "completed",
            "status": "interview_completed",
            "completed_at": _now(),
            "updated_at": _now(),
        },
    )


def mark_interview_abandoned(application_id: str) -> None:
    candidate = get_candidate_by_application_id(application_id)

    if not candidate:
        return

    questions = _five_questions(candidate.get("questions"))
    _update_candidate(
        application_id,
        {
            "questions": questions,
            "total_score": _total_score(questions),
            "max_score": 50,
            "interview_status": "abandoned",
            "status": "interview_in_progress",
            "updated_at": _now(),
        },
    )


def candidate_invite_state(candidate: dict) -> dict:
    aadhaar_verified = candidate.get("aadhaar_verified") is True
    face_verified = candidate.get("face_verified") is True
    interview_status = candidate.get("interview_status") or "not_started"

    if not aadhaar_verified:
        next_step = "aadhaar"
    elif not face_verified:
        next_step = "face"
    elif interview_status != "completed":
        next_step = "interview"
    else:
        next_step = "completed"

    return {
        "application_id": candidate.get("application_id"),
        "candidate_name": candidate.get("candidate_name") or "Candidate",
        "resume_file": candidate.get("resume_file"),
        "ats_score": candidate.get("ats_score"),
        "ats_status": candidate.get("ats_status"),
        "status": candidate.get("status"),
        "aadhaar_verified": aadhaar_verified,
        "face_verified": face_verified,
        "interview_status": interview_status,
        "next_step": next_step,
    }


def _update_candidate(application_id: str, updates: dict) -> None:
    get_collection().update_one(
        {"application_id": str(application_id), "deleted": {"$ne": True}},
        {"$set": updates},
        upsert=False,
    )


def _question_document(question: dict) -> dict:
    return {
        "question_id": str(question.get("id") or question.get("question_id") or ""),
        "question_text": question.get("question") or question.get("question_text") or "",
        "difficulty": str(question.get("difficulty") or "").lower(),
        "audio_file_path": None,
        "transcript_file_path": None,
        "transcript": "",
        "score": 0,
        "feedback": "",
        "evaluation": {},
        "submitted_at": None,
        "answered": False,
    }


def _answer_to_question_document(answer: dict) -> dict:
    return {
        "question_id": str(answer.get("question_id") or ""),
        "question_text": answer.get("question_text") or "",
        "difficulty": str(answer.get("difficulty") or "").lower(),
        "audio_file_path": answer.get("audio_file_path"),
        "transcript_file_path": answer.get("transcript_file_path"),
        "transcript": answer.get("transcript") or "",
        "score": _number(answer.get("score"), 0),
        "feedback": answer.get("feedback") or "",
        "evaluation": answer.get("evaluation") or {},
        "submitted_at": answer.get("submitted_at") or _now(),
        "answered": True,
    }


def _five_questions(value) -> list[dict]:
    questions = value if isinstance(value, list) else []
    normalized = []

    for question in questions[:5]:
        if not isinstance(question, dict):
            continue

        normalized.append(
            {
                **question,
                "transcript": question.get("transcript") or "",
                "score": _number(question.get("score"), 0),
                "feedback": question.get("feedback") or "",
                "answered": bool(question.get("answered") or question.get("submitted_at") or question.get("transcript")),
            }
        )

    while len(normalized) < 5:
        index = len(normalized) + 1
        normalized.append(
            {
                "question_id": f"q{index}",
                "question_text": "",
                "difficulty": "",
                "audio_file_path": None,
                "transcript_file_path": None,
                "transcript": "",
                "score": 0,
                "feedback": "",
                "evaluation": {},
                "submitted_at": None,
                "answered": False,
            }
        )

    return normalized


def _total_score(questions: list[dict]) -> int | float:
    total = sum(_number(question.get("score"), 0) for question in questions if isinstance(question, dict))
    return int(total) if float(total).is_integer() else round(total, 1)


def _candidate_name(application: dict) -> str:
    return (
        application.get("candidate_name")
        or _safe_get(application, ["resume", "candidate_name"])
        or application.get("file_name")
        or "Candidate"
    )


def _safe_get(mapping: dict, keys: list[str]):
    current = mapping

    for key in keys:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def _number(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _serialize(document):
    if not document:
        return None

    serialized = {}

    for key, value in document.items():
        serialized[key] = str(value) if isinstance(value, ObjectId) else value

    return serialized


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
