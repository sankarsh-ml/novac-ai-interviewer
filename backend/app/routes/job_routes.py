import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from io import BytesIO
from fastapi.responses import FileResponse,Response
from fastapi import HTTPException

from app.services.candidate_report_service import (
    generate_candidate_report_pdf,
    generate_candidate_reports_pdf,
    group_report_filename,
    is_report_ready,
    report_filename,
)
from app.services.db_service import (
    delete_application,
    delete_job_records,
    get_all_jobs,
    get_application_by_id,
    list_applications,
    quick_select_job_applications,
    update_application,
    save_job,
    delete_job,
)
from app.routes.interview_routes import finalize_partial_interview


router = APIRouter()


class JobRequest(BaseModel):
    title: str
    description: str = ""
    required_skills: list[str]
    education: str
    experience: int
    keywords: list[str]


class BulkReportRequest(BaseModel):
    application_ids: list[str] = []
    job_id: str = ""

class HRDecisionRequest(BaseModel):
    decision: str

class QuickSelectRequest(BaseModel):
    count: Any = None

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
    applications = [
        _finalize_if_partial_or_quit(application)
        for application in list_applications()
    ]
    response = {
        "success": True,
        "applications": applications,
    }
    print(f"[HR candidate details] response={json.dumps(response, ensure_ascii=False)}")
    return response


@router.get("/applications/{application_id}")
def fetch_application(application_id: str):
    application = get_application_by_id(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    application = _finalize_if_partial_or_quit(application)
    response = {
        "success": True,
        "application": application,
    }
    print(f"[HR candidate details] response={json.dumps(response, ensure_ascii=False)}")
    return response


@router.get("/jobs/{job_id}/applications")
def fetch_job_applications(job_id: str):
    applications = [
        _finalize_if_partial_or_quit(application)
        for application in list_applications()
        if str(application.get("job_id") or "") == str(job_id)
    ]
    response = {
        "success": True,
        "applications": applications,
    }
    print(f"[HR candidate details] response={json.dumps(response, ensure_ascii=False)}")
    return response

@router.delete("/jobs/{job_id}")
def remove_job(job_id: str):

    if not delete_job(job_id):
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    return {
        "success": True,
        "message": "Job and all associated data deleted."
    }


@router.post("/jobs/{job_id}/quick-select")
def quick_select_candidates(job_id: str, request: QuickSelectRequest):
    count = _parse_quick_select_count(request.count)

    if count is None:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Count must be a valid number greater than zero.",
            },
        )

    if count <= 0:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Count must be greater than zero.",
            },
        )

    print(f"[HR quick-select] job_id={job_id} requested_count={count}")
    result = quick_select_job_applications(job_id, count)
    selected_count = result["selected_count"]

    if not result["success"]:
        print(
            "[HR quick-select] "
            f"job_id={job_id} rejected request available_count={result['available_count']} requested_count={count}"
        )
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "selected_count": 0,
                "available_count": result["available_count"],
                "applications": result["applications"],
                "candidates": result["applications"],
                "message": result["message"],
            },
        )

    print(
        "[HR quick-select] "
        f"job_id={job_id} selected_count={selected_count} updated_count={result['updated_count']}"
    )

    return {
        "success": True,
        "selected_count": selected_count,
        "updated_count": result["updated_count"],
        "applications": result["applications"],
        "candidates": result["applications"],
        "message": _quick_select_message(selected_count),
    }


@router.delete("/jobs/{job_id}/records")
def remove_job_records(job_id: str):
    print(f"[HR delete-records] job_id={job_id} started")
    deleted_count = delete_job_records(job_id)
    print(f"[HR delete-records] job_id={job_id} deleted_count={deleted_count}")

    return {
        "success": True,
        "deleted_count": deleted_count,
        "message": "All records deleted successfully.",
    }



@router.get("/applications/{application_id}/report")
def download_candidate_report(application_id: str):
    application = get_application_by_id(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    application = _finalize_if_partial_or_quit(application)

    if not is_report_ready(application):
        raise HTTPException(
            status_code=400,
            detail="Candidate report is available after a completed, partial, or quit interview attempt.",
        )

    pdf_bytes = generate_candidate_report_pdf(application)
    filename = report_filename(application)
    return _pdf_response(pdf_bytes, filename)


@router.post("/reports")
def download_candidate_reports(payload: BulkReportRequest):
    applications = _resolve_report_applications(payload)

    if not applications:
        raise HTTPException(status_code=400, detail="No completed, partial, or quit candidates selected for report generation.")

    incomplete = [
        str(application.get("application_id") or application.get("_id") or "unknown")
        for application in applications
        if not is_report_ready(application)
    ]

    if incomplete:
        raise HTTPException(
            status_code=400,
            detail=f"Reports can be generated only for completed, partial, or quit interviews: {', '.join(incomplete)}",
        )

    pdf_bytes = generate_candidate_reports_pdf(applications)
    return _pdf_response(pdf_bytes, group_report_filename())


@router.delete("/applications/{application_id}")
def remove_application(application_id: str):
    if not delete_application(application_id):
        raise HTTPException(status_code=404, detail="Application not found")

    return {
        "success": True,
        "message": "Application and local artifacts deleted",
    }

@router.get("/applications/{application_id}/resume/download")
def download_application_resume(application_id: str):
    application = get_application_by_id(application_id)

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    return FileResponse(
        path=application["file_path"],
        media_type="application/pdf",
        filename=application["file_name"]
    )

@router.get("/applications/{application_id}/resume/view")
def view_application_resume(application_id: str):

    application = get_application_by_id(application_id)

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    with open(application["file_path"], "rb") as pdf_file:
        pdf_bytes = pdf_file.read()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "inline"
        }
    )

@router.patch("/applications/{application_id}/hr-decision")
def update_hr_decision(
    application_id: str,
    request: HRDecisionRequest,
):
    if request.decision not in ["pending", "selected", "rejected"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid decision."
        )

    success = update_application(
        application_id,
        {
            "hr_decision": request.decision
        },
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Application not found."
        )

    return {
        "success": True,
        "message": "HR decision updated."
    }

def _resolve_report_applications(payload: BulkReportRequest) -> list[dict]:
    requested_ids = [str(application_id).strip() for application_id in payload.application_ids if str(application_id).strip()]

    if requested_ids:
        applications = []
        missing_ids = []

        for application_id in requested_ids:
            application = get_application_by_id(application_id)

            if application:
                applications.append(_finalize_if_partial_or_quit(application))
            else:
                missing_ids.append(application_id)

        if missing_ids:
            raise HTTPException(status_code=404, detail=f"Applications not found: {', '.join(missing_ids)}")

        return applications

    job_id = str(payload.job_id or "").strip()

    if not job_id:
        return []

    return [
        _finalize_if_partial_or_quit(application)
        for application in list_applications()
        if str(application.get("job_id") or "") == job_id and is_report_ready(application)
    ]


def _finalize_if_partial_or_quit(application: dict) -> dict:
    status = str(application.get("interview_status") or application.get("interviewStatus") or "").lower()

    if status not in {"partial", "quit", "interrupted"}:
        return application

    application_id = str(application.get("application_id") or application.get("_id") or "")

    if not application_id:
        return application

    return finalize_partial_interview(application_id, status=status) or application


def _parse_quick_select_count(value) -> int | None:
    if isinstance(value, bool) or value is None:
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value) if value.is_integer() else None

    text = str(value).strip()

    if not text or not text.isdigit():
        return None

    return int(text)


def _quick_select_message(selected_count: int) -> str:
    if selected_count == 0:
        return "No new candidates were selected."

    noun = "candidate" if selected_count == 1 else "candidates"
    return f"Selected {selected_count} {noun} successfully."


def _pdf_response(pdf_bytes: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
