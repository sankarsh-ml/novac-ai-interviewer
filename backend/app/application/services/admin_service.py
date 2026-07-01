from __future__ import annotations

import os
import secrets

from app.infrastructure.database.mongo_service import mongo_now
from app.repositories import admin_repository


def hash_password(password: str) -> str:
    return str(password or "")


def verify_password(password: str, stored_password: str) -> bool:
    return str(password or "") == str(stored_password or "")


def create_or_update_admin(username: str, password: str, role: str = "admin") -> bool:
    username = str(username or "").strip()
    password = str(password or "")

    if not username or not password:
        return False

    now = mongo_now()
    admin_id = secrets.token_hex(16)
    admin_repository.upsert_admin_user(
        username,
        {
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
        {
            "adminId": admin_id,
            "admin_id": admin_id,
            "createdAt": now,
            "created_at": now,
        },
    )
    return True


def authenticate_admin(username: str, password: str) -> bool:
    username = str(username or "").strip()
    password = str(password or "")

    if not username or not password:
        return False

    user = admin_repository.get_by_username(username)

    if not user or user.get("isActive") is False or user.get("is_active") is False:
        return False

    stored_password = user.get("password") or user.get("passwordHash") or user.get("password_hash")

    if not verify_password(password, stored_password):
        return False

    admin_repository.mark_login(username)
    return True


def login(username: str, password: str) -> bool:
    return authenticate_admin(username, password)


def create_admin(username: str, password: str, role: str = "admin") -> bool:
    return create_or_update_admin(username, password, role)


def seed_default_admin() -> None:
    if admin_repository.count_admin_users() > 0:
        return

    username = os.getenv("ADMIN_USERNAME", "admin1")
    password = os.getenv("ADMIN_PASSWORD", "admin12345")
    create_or_update_admin(username, password)
    print(f"[AdminAuth] Seeded DEV plaintext admin username={username}")
