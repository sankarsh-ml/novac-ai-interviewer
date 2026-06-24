from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.db_service import candidate_invite_state, find_application_by_invite_token
from app.services.mongo_interview_service import (
    candidate_invite_state as mongo_candidate_invite_state,
    get_candidate_by_token,
)


router = APIRouter()


@router.get("/invite/{token}")
def fetch_candidate_invite(token: str):
    candidate = get_candidate_by_token(token)

    if candidate:
        return {
            "success": True,
            **mongo_candidate_invite_state(candidate),
        }

    application = find_application_by_invite_token(token)

    if not application:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": "Invalid or expired interview link",
            },
        )

    return {
        "success": True,
        **candidate_invite_state(application),
    }
