from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.db_service import update_application

from app.services.ats_engine import calculate_ats
from app.services.db_service import (
    get_application_by_id,
    get_job_by_id,
    update_ats_decision,
)


router = APIRouter()


class AtsDecisionRequest(BaseModel):
    decision: str


@router.get("/score/{application_id}")
def score_resume(application_id: str):
    application = get_application_by_id(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    job_id = application.get("job_id")
    job = get_job_by_id(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found for this application")

    sections = _get_sections(application)
    resume_data = {
        "data": {
            "candidate_name": _get_candidate_name(application),
            "skills": _section_items(sections, "skills"),
            "education": _section_items(sections, "education"),
            "projects": _section_items(sections, "projects"),
            "experience": _section_items(sections, "experience"),
            "raw_text": _get_resume_text(application),
        }
    }

    result = calculate_ats(resume_data, job)
    decision = result.get("status") or ("passed" if result.get("passed") else "failed")
    update_application(
            application_id,
            {
                "ats_score":
                    result.get("atsScore"),

                "semantic_score":
                    result.get("semantic_score"),

                "skill_score":
                    result.get("skill_score"),

                "education_score":
                    result.get("education_score"),

                "experience_score":
                    result.get("experience_score"),

                "project_score":
                    result.get("project_score"),

                "ats_status":
                    decision
            }
        )
    update_ats_decision(application_id, decision)

    return {
        "success": True,
        "ats_score": result.get("ats_score"),
        "matched_skills": result.get("matched_skills", []),
        "missing_skills": result.get("missing_skills", []),
        "candidate_name": result.get("candidate_name"),
        "passed": result.get("passed", False),
        "status": decision,
        "ats_status": decision,
        "result": result,
        "data": {
            "application_id": application_id,
            "ats_status": decision,
            "next_step": "aadhaar_verification" if decision == "passed" else "stop",
        },
    }


@router.post("/{application_id}/decision")
def save_ats_decision(application_id: str, request: AtsDecisionRequest):
    decision = request.decision.lower().strip()

    if decision not in {"passed", "failed"}:
        raise HTTPException(status_code=400, detail="Decision must be passed or failed")

    was_updated = update_ats_decision(application_id, decision)

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


def _get_sections(application: dict) -> dict:
    return (
        application.get("ats_ready_data", {}).get("sections_detected")
        or application.get("resume", {}).get("ats_ready_data", {}).get("sections_detected")
        or {}
    )


def _section_items(sections: dict, section_name: str) -> list:
    section = sections.get(section_name, {})

    if isinstance(section, dict):
        return section.get("items", [])

    if isinstance(section, list):
        return section

    return []


def _get_candidate_name(application: dict) -> str:
    return (
        application.get("candidate_name")
        or application.get("resume", {}).get("candidate_name")
        or application.get("file_name")
        or "Candidate"
    )


def _get_resume_text(application: dict) -> str:
    return (
        application.get("extracted_text")
        or application.get("ats_ready_data", {}).get("raw_text")
        or application.get("ats_ready_data", {}).get("normalized_text")
        or application.get("resume", {}).get("extracted_text")
        or application.get("resume", {}).get("ats_ready_data", {}).get("raw_text")
        or application.get("resume", {}).get("ats_ready_data", {}).get("normalized_text")
        or ""
    )
