from __future__ import annotations

from app.infrastructure.database.mongo_service import get_database, make_json_safe, mongo_now, public_document


def replace_for_job(job_id: str, questions: list[dict]) -> None:
    db = get_database()
    db.question_bank.delete_many(_job_query(job_id))

    if questions:
        db.question_bank.insert_many(
            [
                {
                    **make_json_safe(question),
                    "questionId": question.get("question_id") or question.get("id") or question.get("_id"),
                    "jobId": str(job_id or ""),
                    "job_id": str(job_id or ""),
                    "createdAt": question.get("createdAt") or question.get("created_at") or mongo_now(),
                    "updatedAt": mongo_now(),
                }
                for question in questions
            ]
        )


def list_for_job(job_id: str) -> list[dict]:
    query = _job_or_global_query(job_id) if str(job_id or "").strip() else {}
    documents = get_database().question_bank.find(query).sort("created_at", 1)
    return [item for item in (public_document(document) for document in documents) if item]


def clear_for_job(job_id: str) -> int:
    return get_database().question_bank.delete_many(_job_query(job_id)).deleted_count


def _job_query(job_id: str) -> dict:
    return {"$or": [{"job_id": str(job_id or "")}, {"jobId": str(job_id or "")}]}


def _job_or_global_query(job_id: str) -> dict:
    value = str(job_id or "")
    return {
        "$or": [
            {"job_id": value},
            {"jobId": value},
            {"job_id": ""},
            {"jobId": ""},
            {"job_id": {"$exists": False}},
            {"jobId": {"$exists": False}},
        ]
    }
