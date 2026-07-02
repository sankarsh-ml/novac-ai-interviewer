from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.application.services.candidate_auth_service import issue_candidate_token, require_candidate_jwt

router = APIRouter(prefix="/candidate", tags=["Candidate Auth"])


class CandidateTokenRequest(BaseModel):
    interviewLinkToken: str = ""
    token: str = ""


@router.post("/token")
@router.post("/auth/token")
def create_candidate_token(payload: CandidateTokenRequest):
    return issue_candidate_token(payload.interviewLinkToken or payload.token)


@router.get("/debug/context")
def candidate_debug_context(current_candidate: dict = Depends(require_candidate_jwt)):
    return {
        "candidateId": current_candidate.get("candidateId") or "",
        "jobId": current_candidate.get("jobId") or "",
        "interviewId": current_candidate.get("interviewId") or "",
        "role": current_candidate.get("role") or "candidate",
    }
