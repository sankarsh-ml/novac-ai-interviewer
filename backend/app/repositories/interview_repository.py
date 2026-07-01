from __future__ import annotations

from datetime import datetime

from app.infrastructure.database.mongo_service import get_database, public_document


def upsert_interview_for_candidate(candidate_id: str, data: dict, insert_defaults: dict | None = None) -> None:
    get_database().interviews.update_one(
        {"candidateId": candidate_id},
        {
            "$set": {
                **data,
                "candidateId": candidate_id,
                "application_id": candidate_id,
                "updatedAt": datetime.now().isoformat(),
            },
            "$setOnInsert": insert_defaults or {"createdAt": datetime.now().isoformat()},
        },
        upsert=True,
    )


def get_link_by_token(token: str) -> dict | None:
    if not token:
        return None

    return public_document(
        get_database().interviews.find_one({"$or": [{"token": token}, {"interviewLinkToken": token}]})
    )


def mark_link_used(token: str) -> None:
    if not token:
        return

    get_database().interviews.update_one(
        {"$or": [{"token": token}, {"interviewLinkToken": token}]},
        {"$set": {"used": True, "updatedAt": datetime.now().isoformat()}},
    )
