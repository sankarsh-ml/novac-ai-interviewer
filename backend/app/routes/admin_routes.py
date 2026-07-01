from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.application.services.admin_service import login as admin_login

router = APIRouter(prefix="/admin", tags=["Admin"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(request: LoginRequest):

    if admin_login(request.username, request.password):
        return {
            "success": True,
            "message": "Login successful"
        }

    return JSONResponse(
        status_code=401,
        content={
            "success": False,
            "message": "Invalid username or password",
        },
    )
