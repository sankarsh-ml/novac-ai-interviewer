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
    description: str
    required_skills: list[str]
    education: str
    experience: int
    keywords: list[str]

@router.post("/jobs")
def create_job(job: JobRequest):
    job_id = save_job(
        {
            "title": job.title,
            "description": job.description,
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

@router.get("/jobs/{job_id}/applications")
def get_job_applications(job_id: str):

    applications = list_applications()

    filtered = [
        app
        for app in applications
        if app.get("job_id") == job_id
    ]

    return {
        "success": True,
        "applications": filtered
    }