from __future__ import annotations

from app.infrastructure.database.mongo_service import get_database, public_document


def get_by_id(job_id: str) -> dict | None:
    return public_document(get_database().jobs.find_one(_job_filter(job_id)))


def list_all() -> list[dict]:
    return [item for item in (public_document(doc) for doc in get_database().jobs.find({}).sort("created_at", -1)) if item]


def insert(document: dict) -> None:
    get_database().jobs.insert_one(document)


def delete(job_id: str) -> int:
    return get_database().jobs.delete_one(_job_filter(job_id)).deleted_count


def _job_filter(job_id: str) -> dict:
    return {"$or": [{"id": str(job_id)}, {"jobId": str(job_id)}, {"job_id": str(job_id)}]}
