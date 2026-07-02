from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.infrastructure.database.mongo_service import mongo_now
from app.repositories import admin_repository

DEV_JWT_SECRET = "novac-development-jwt-secret-change-me"
bearer_scheme = HTTPBearer(scheme_name="BearerAuth", auto_error=False)
_jwt_warning_logged = False


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


def authenticate_admin_user(username: str, password: str) -> dict | None:
    username = str(username or "").strip()
    password = str(password or "")

    if not username or not password:
        return None

    user = admin_repository.get_by_username(username)

    if not user or user.get("isActive") is False or user.get("is_active") is False:
        return None

    stored_password = user.get("password") or user.get("passwordHash") or user.get("password_hash")

    if not verify_password(password, stored_password):
        return None

    admin_repository.mark_login(username)
    return user


def authenticate_admin(username: str, password: str) -> bool:
    return authenticate_admin_user(username, password) is not None


def login(username: str, password: str) -> bool:
    return authenticate_admin(username, password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    payload = dict(data or {})
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=_jwt_expire_minutes()))
    payload.update({"exp": expire})
    return jwt.encode(payload, _jwt_secret_key(), algorithm=_jwt_algorithm())


def decode_access_token(token: str, detail: str = "Invalid or expired token") -> dict:
    try:
        return jwt.decode(token, _jwt_secret_key(), algorithms=[_jwt_algorithm()])
    except JWTError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


def create_admin_token(user: dict) -> str:
    username = str(user.get("username") or "")
    role = str(user.get("role") or "admin")
    admin_id = str(user.get("adminId") or user.get("admin_id") or "")
    return create_access_token({"sub": username, "role": role, "adminId": admin_id})


def get_current_admin_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    token = _bearer_token(credentials, query_token=request.query_params.get("access_token"))
    payload = decode_access_token(token)

    if payload.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin token required")

    username = str(payload.get("sub") or "").strip()

    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = admin_repository.get_by_username(username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.get("isActive") is False or user.get("is_active") is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin user is inactive")

    return user


def require_admin_jwt(current_admin: dict = Depends(get_current_admin_user)) -> dict:
    return current_admin


def require_admin(current_admin: dict = Depends(require_admin_jwt)) -> dict:
    return current_admin


def create_admin(username: str, password: str, role: str = "admin") -> bool:
    return create_or_update_admin(username, password, role)


def seed_default_admin() -> None:
    if admin_repository.count_admin_users() > 0:
        return

    username = os.getenv("ADMIN_USERNAME", "admin1")
    password = os.getenv("ADMIN_PASSWORD", "admin12345")
    create_or_update_admin(username, password)
    print(f"[AdminAuth] Seeded DEV plaintext admin username={username}")


def _jwt_secret_key() -> str:
    global _jwt_warning_logged

    secret = os.getenv("JWT_SECRET_KEY")

    if secret:
        return secret

    if not _jwt_warning_logged:
        print("[Auth] WARNING: Using development JWT secret. Set JWT_SECRET_KEY for production.")
        _jwt_warning_logged = True

    return DEV_JWT_SECRET


def _jwt_algorithm() -> str:
    return os.getenv("JWT_ALGORITHM", "HS256") or "HS256"


def _jwt_expire_minutes() -> int:
    try:
        return int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    except (TypeError, ValueError):
        return 1440


def _bearer_token(
    credentials: HTTPAuthorizationCredentials | None,
    detail: str = "Invalid or expired token",
    query_token: str | None = None,
) -> str:
    if query_token:
        return str(query_token)

    if not credentials or str(credentials.scheme or "").lower() != "bearer" or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials
