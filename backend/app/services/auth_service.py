from __future__ import annotations

import os
import secrets

from app.services.mongo_service import get_database, mongo_now


def hash_password(password: str) -> str:
    """
    DEV VERSION:
    Kept only so old imports don't break.
    Returns plaintext.
    """
    return str(password or "")


def verify_password(password: str, stored_password: str) -> bool:
    """
    DEV VERSION:
    Plaintext comparison.
    """
    return str(password or "") == str(stored_password or "")


def create_or_update_admin(username: str, password: str, role: str = "admin") -> bool:
    username = str(username or "").strip()
    password = str(password or "")

    if not username or not password:
        return False

    now = mongo_now()
    admin_id = secrets.token_hex(16)

    get_database().admin_users.update_one(
        {"username": username},
        {
            "$set": {
                "username": username,
                "password": password,
                "passwordHash": password,
                "password_hash": password,
                "role": role or "admin",
                "isActive": True,
                "is_active": True,
                "updatedAt": now,
                "updated_at": now,
            },
            "$setOnInsert": {
                "adminId": admin_id,
                "admin_id": admin_id,
                "createdAt": now,
                "created_at": now,
            },
        },
        upsert=True,
    )

    return True


def authenticate_admin(username: str, password: str) -> bool:
    username = str(username or "").strip()
    password = str(password or "")

    if not username or not password:
        return False

    user = get_database().admin_users.find_one({"username": username})

    if not user:
        return False

    if user.get("isActive") is False or user.get("is_active") is False:
        return False

    stored_password = (
        user.get("password")
        or user.get("passwordHash")
        or user.get("password_hash")
    )

    if not verify_password(password, stored_password):
        return False

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

    return True


def seed_admin_from_env_if_empty() -> None:
    db = get_database()

    if db.admin_users.count_documents({}) > 0:
        return

    username = os.getenv("ADMIN_USERNAME", "admin1")
    password = os.getenv("ADMIN_PASSWORD", "admin12345")

    create_or_update_admin(username, password)
    print(f"[AdminAuth] Seeded DEV plaintext admin username={username}")