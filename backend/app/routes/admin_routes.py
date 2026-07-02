from fastapi import APIRouter
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends
from pydantic import BaseModel

from app.application.services.admin_service import authenticate_admin_user, create_admin_token

router = APIRouter(prefix="/admin", tags=["Admin"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(request: LoginRequest):
    user = authenticate_admin_user(request.username, request.password)

    if user:
        access_token = create_admin_token(user)
        return {
            "success": True,
            "message": "Login successful",
            "access_token": access_token,
            "token_type": "bearer",
            "admin": _public_admin(user),
        }

    return JSONResponse(
        status_code=401,
        content={
            "success": False,
            "message": "Invalid username or password",
        },
    )


@router.post("/token")
def token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_admin_user(form_data.username, form_data.password)

    if not user:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "message": "Invalid username or password",
            },
        )

    return {
        "access_token": create_admin_token(user),
        "token_type": "bearer",
    }


def _public_admin(user: dict) -> dict:
    return {
        "username": user.get("username") or "",
        "role": user.get("role") or "admin",
        "adminId": user.get("adminId") or user.get("admin_id") or "",
    }
