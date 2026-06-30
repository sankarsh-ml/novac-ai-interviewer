from fastapi import APIRouter
from pydantic import BaseModel

from app.services.admin_auth_service import authenticate

router = APIRouter(prefix="/admin", tags=["Admin"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(request: LoginRequest):

    if authenticate(request.username, request.password):
        return {
            "success": True,
            "message": "Login successful"
        }

    return {
        "success": False,
        "message": "Invalid username or password"
    }