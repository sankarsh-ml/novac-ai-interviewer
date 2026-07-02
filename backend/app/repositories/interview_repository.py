from __future__ import annotations

from datetime import datetime

from app.infrastructure.database.mongo_service import get_database, public_document


def upsert_interview_for_candidate(candidate_id: str, data: dict, insert_defaults: dict | None = None) -> None:
    interview_id = str(data.get("interviewId") or data.get("interview_id") or data.get("token") or data.get("interviewLinkToken") or "")
    filter_query = {"candidateId": candidate_id}
    set_on_insert = insert_defaults or {"createdAt": datetime.now().isoformat()}
    set_values = {
        **data,
        "interviewId": interview_id or data.get("interviewId"),
        "candidateId": candidate_id,
        "application_id": candidate_id,
        "updatedAt": datetime.now().isoformat(),
    }

    for key in set_on_insert:
        set_values.pop(key, None)

    if interview_id:
        filter_query = {"candidateId": candidate_id, "interviewId": interview_id}

    get_database().interviews.update_one(
        filter_query,
        {
            "$set": set_values,
            "$setOnInsert": set_on_insert,
        },
        upsert=True,
    )


def get_interview_by_id(interview_id: str) -> dict | None:
    if not interview_id:
        return None

    return public_document(
        get_database().interviews.find_one(
            {
                "$or": [
                    {"interviewId": str(interview_id)},
                    {"interview_id": str(interview_id)},
                    {"token": str(interview_id)},
                    {"interviewLinkToken": str(interview_id)},
                ]
            }
        )
    )


def update_interview_attempt(interview_id: str, updates: dict) -> None:
    if not interview_id:
        return

    get_database().interviews.update_one(
        {
            "$or": [
                {"interviewId": str(interview_id)},
                {"interview_id": str(interview_id)},
                {"token": str(interview_id)},
                {"interviewLinkToken": str(interview_id)},
            ]
        },
        {"$set": {**updates, "updatedAt": datetime.now().isoformat()}},
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
