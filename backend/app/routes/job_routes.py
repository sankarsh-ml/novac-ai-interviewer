import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.db_service import (
    delete_application,
    get_all_jobs,
    get_application_by_id,
    list_applications,
    save_job,
)


router = APIRouter()


class JobRequest(BaseModel):
    title: str
    description: str = ""
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
    response = {
        "success": True,
        "applications": list_applications(),
    }
    print(f"[HR candidate details] response={json.dumps(response, ensure_ascii=False)}")
    return response


@router.get("/applications/{application_id}")
def fetch_application(application_id: str):
    application = get_application_by_id(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    response = {
        "success": True,
        "application": application,
    }
    print(f"[HR candidate details] response={json.dumps(response, ensure_ascii=False)}")
    return response


@router.get("/jobs/{job_id}/applications")
def fetch_job_applications(job_id: str):
    response = {
        "success": True,
        "applications": [
            application
            for application in list_applications()
            if str(application.get("job_id") or "") == str(job_id)
        ],
    }
    print(f"[HR candidate details] response={json.dumps(response, ensure_ascii=False)}")
    return response


@router.delete("/applications/{application_id}")
def remove_application(application_id: str):
    if not delete_application(application_id):
        raise HTTPException(status_code=404, detail="Application not found")

    return {
        "success": True,
        "message": "Application and local artifacts deleted",
    }
