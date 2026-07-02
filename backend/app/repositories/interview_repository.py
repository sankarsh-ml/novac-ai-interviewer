from __future__ import annotations

from datetime import datetime

from app.infrastructure.database.mongo_service import get_database, public_document
from app.utils.interview_tokens import generate_interview_token, normalize_interview_token_fields

try:
    from pymongo.errors import DuplicateKeyError
except Exception:  # pragma: no cover - pymongo is optional until MongoDB is used.
    class DuplicateKeyError(Exception):
        pass


def upsert_interview_for_candidate(candidate_id: str, data: dict, insert_defaults: dict | None = None) -> None:
    data, unset_fields = normalize_interview_token_fields(data, generate_missing=True)
    interview_id = str(data.get("interviewId") or data.get("interview_id") or data.get("interviewLinkToken") or "")
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

    update = {
        "$set": set_values,
        "$setOnInsert": set_on_insert,
    }

    if unset_fields:
        update["$unset"] = unset_fields

    db = get_database()

    for attempt in range(3):
        try:
            db.interviews.update_one(filter_query, update, upsert=True)
            return
        except DuplicateKeyError:
            if attempt >= 2:
                raise

            retry_token = generate_interview_token()
            set_values["interviewLinkToken"] = retry_token
            update["$set"] = set_values


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
                    {"linkToken": str(interview_id)},
                    {"interview_token": str(interview_id)},
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
                {"linkToken": str(interview_id)},
                {"interview_token": str(interview_id)},
                {"interviewLinkToken": str(interview_id)},
            ]
        },
        {"$set": {**updates, "updatedAt": datetime.now().isoformat()}},
    )


def get_link_by_token(token: str) -> dict | None:
    if not token:
        return None

    db = get_database()
    fields = ("interviewLinkToken", "token", "linkToken", "interview_token")

    for field in fields:
        document = public_document(db.interviews.find_one({field: token}))

        if document:
            document["_matchedBy"] = field
            return document

    return None


def mark_link_used(token: str) -> None:
    if not token:
        return

    get_database().interviews.update_one(
        {
            "$or": [
                {"interviewLinkToken": token},
                {"token": token},
                {"linkToken": token},
                {"interview_token": token},
            ]
        },
        {"$set": {"used": True, "updatedAt": datetime.now().isoformat()}},
    )
