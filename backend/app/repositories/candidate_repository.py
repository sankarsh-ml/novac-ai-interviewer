from __future__ import annotations

from app.infrastructure.database.mongo_service import get_database, public_document


def application_filter(application_id: str) -> dict:
    return {
        "$or": [
            {"application_id": str(application_id)},
            {"candidateId": str(application_id)},
            {"candidate_id": str(application_id)},
        ]
    }


def job_filter(job_id: str) -> dict:
    return {"$or": [{"job_id": str(job_id)}, {"jobId": str(job_id)}]}


def get_by_id(application_id: str) -> dict | None:
    return public_document(get_database().candidates.find_one(application_filter(application_id)))


def list_for_job(job_id: str) -> list[dict]:
    return [item for item in (public_document(doc) for doc in get_database().candidates.find(job_filter(job_id))) if item]


def insert(document: dict) -> None:
    get_database().candidates.insert_one(document)


def update(application_id: str, updates: dict) -> int:
    return get_database().candidates.update_one(application_filter(application_id), {"$set": updates}).matched_count


def delete(application_id: str) -> int:
    return get_database().candidates.delete_one(application_filter(application_id)).deleted_count
