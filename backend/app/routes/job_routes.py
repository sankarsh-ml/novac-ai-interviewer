from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.db_service import (
    get_all_jobs,
    get_application_by_id,
    list_applications,
    save_job,
)


router = APIRouter()


class JobRequest(BaseModel):
    title: str
    required_skills: list[str]
    education: str
    experience: int
    keywords: list[str]


@router.post("/jobs")
def create_job(job: JobRequest):
    job_id = save_job(
        {
            "title": job.title,
            "required_skills": job.required_skills,
            "education": job.education,
            "experience": job.experience,
            "keywords": job.keywords,
        }
    )

    return {
        "success": True,
        "job_id": job_id,
        "message": "Job created successfully",
    }


@router.get("/jobs")
def fetch_jobs():
    return {
        "success": True,
        "jobs": get_all_jobs(),
    }


@router.get("/applications")
def fetch_applications():
    return {
        "success": True,
        "applications": list_applications(),
    }


@router.get("/applications/{application_id}")
def fetch_application(application_id: str):
    application = get_application_by_id(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    return {
        "success": True,
        "application": application,
    }
