from __future__ import annotations

from app.infrastructure.database.mongo_service import get_database


def upsert_identity_verification(candidate_id: str, document: dict) -> None:
    get_database().identity_verifications.update_one(
        {"candidateId": candidate_id},
        {"$set": document},
        upsert=True,
    )


def delete_many(filter_query: dict) -> int:
    return get_database().identity_verifications.delete_many(filter_query).deleted_count
