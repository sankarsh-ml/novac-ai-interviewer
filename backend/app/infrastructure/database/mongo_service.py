from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi.encoders import jsonable_encoder

from app.core.config import get_database_config
from app.infrastructure.database.mongo_indexes import ensure_indexes as ensure_mongo_indexes

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

    database_config = get_database_config()
    mongo_uri = database_config["mongo_uri"]
    db_name = database_config["db_name"]

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
        ensure_mongo_indexes(_db)
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
