from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any

from fastapi.encoders import jsonable_encoder


DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_DB_NAME = "novac_ai_interview"

_client = None
_db = None
_indexes_ensured = False


class DatabaseUnavailableError(RuntimeError):
    pass


def get_database():
    global _client, _db

    if _db is not None:
        return _db

    try:
        from pymongo import MongoClient
    except Exception as error:
        raise DatabaseUnavailableError("Database unavailable. Please start MongoDB and try again.") from error

    mongo_uri = os.getenv("MONGO_URI", DEFAULT_MONGO_URI)
    db_name = os.getenv("MONGO_DB_NAME", DEFAULT_DB_NAME)

    try:
        _client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        _client.admin.command("ping")
        _db = _client[db_name]
        print(f"[MongoDB] Connected to {db_name}")
        ensure_indexes()
        return _db
    except Exception as error:
        print(f"[MongoDB] Connection failed: {error}")
        _client = None
        _db = None
        raise DatabaseUnavailableError("Database unavailable. Please start MongoDB and try again.") from error


def ensure_indexes() -> None:
    global _indexes_ensured

    if _indexes_ensured or _db is None:
        return

    try:
        _db.jobs.create_index("jobId")
        _db.jobs.create_index("id")
        _db.candidates.create_index("jobId")
        _db.candidates.create_index("job_id")
        _db.candidates.create_index("candidateId")
        _db.candidates.create_index("application_id", unique=True)
        _db.candidates.create_index("email")
        _db.question_bank.create_index("jobId")
        _db.question_bank.create_index("job_id")
        question_indexes = _db.question_bank.index_information()
        question_id_index = question_indexes.get("questionId_1")

        if question_id_index and question_id_index.get("unique"):
            _db.question_bank.drop_index("questionId_1")

        _db.question_bank.create_index("questionId")
        _db.question_bank.create_index("question_id")
        _db.interviews.create_index("interviewId")
        _db.interviews.create_index("candidateId")
        _db.interviews.create_index("application_id")
        _db.interviews.create_index("jobId")
        _db.interviews.create_index("interviewLinkToken")
        _db.interviews.create_index("token", unique=True, sparse=True)
        _db.interview_answers.create_index("interviewId")
        _db.interview_answers.create_index("candidateId")
        _db.interview_answers.create_index("application_id")
        _db.identity_verifications.create_index("candidateId")
        _db.identity_verifications.create_index("application_id")
        _db.reports.create_index("candidateId")
        _db.reports.create_index("jobId")
        _db.admin_users.create_index("username", unique=True)
        _db.admin_users.create_index("adminId")
        _indexes_ensured = True
        print("[MongoDB] Indexes ensured")
    except Exception as error:
        print(f"[MongoDB] Index creation failed: {error}")
        raise DatabaseUnavailableError("Database unavailable. Please start MongoDB and try again.") from error


def close_mongo() -> None:
    global _client, _db, _indexes_ensured

    if _client is not None:
        _client.close()

    _client = None
    _db = None
    _indexes_ensured = False


def mongo_now() -> datetime:
    return datetime.now(timezone.utc)


def make_json_safe(data: Any):
    custom_encoder = {
        datetime: lambda value: value.isoformat(),
        date: lambda value: value.isoformat(),
    }

    try:
        from bson import ObjectId

        custom_encoder[ObjectId] = str
    except Exception:
        pass

    return jsonable_encoder(data, custom_encoder=custom_encoder)


def public_document(document: dict | None) -> dict | None:
    if not isinstance(document, dict):
        return None

    encoded = make_json_safe(document)

    if "_id" in encoded:
        encoded["_id"] = str(encoded["_id"])

    return encoded


def database_unavailable_response() -> dict:
    return {
        "success": False,
        "message": "Database unavailable. Please start MongoDB and try again.",
    }
