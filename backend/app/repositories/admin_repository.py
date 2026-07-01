from __future__ import annotations

from app.infrastructure.database.mongo_service import get_database, mongo_now, public_document


def upsert_admin_user(username: str, document: dict, insert_defaults: dict) -> None:
    get_database().admin_users.update_one(
        {"username": username},
        {"$set": document, "$setOnInsert": insert_defaults},
        upsert=True,
    )


def get_by_username(username: str) -> dict | None:
    return public_document(get_database().admin_users.find_one({"username": username}))


def count_admin_users() -> int:
    return get_database().admin_users.count_documents({})


def mark_login(username: str) -> None:
    now = mongo_now()
    get_database().admin_users.update_one(
        {"username": username},
        {
            "$set": {
                "lastLoginAt": now,
                "last_login_at": now,
                "updatedAt": now,
                "updated_at": now,
            }
        },
    )
