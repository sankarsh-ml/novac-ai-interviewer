from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.db_service import MongoConnectionError, update_ats_status


router = APIRouter()


class AtsDecisionRequest(BaseModel):
    decision: str


@router.post("/{application_id}/decision")
def save_ats_decision(application_id: str, request: AtsDecisionRequest):
    decision = request.decision.lower().strip()

    if decision not in {"passed", "failed"}:
        raise HTTPException(status_code=400, detail="Decision must be passed or failed")

    try:
        was_updated = update_ats_status(application_id, decision)
    except MongoConnectionError as exc:
        raise HTTPException(
            status_code=500,
            detail="MongoDB connection failed. Make sure MongoDB is running.",
        ) from exc

    if not was_updated:
        raise HTTPException(status_code=404, detail="Resume application not found")

    return {
        "success": True,
        "message": "ATS decision saved",
        "data": {
            "application_id": application_id,
            "ats_status": decision,
            "next_step": "aadhaar_verification" if decision == "passed" else "stop",
        },
    }
