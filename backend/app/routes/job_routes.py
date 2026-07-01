import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from io import BytesIO
from fastapi.responses import Response
from fastapi import HTTPException

from app.application.services.report_service import (
    generate_candidate_report_pdf,
    generate_candidate_reports_pdf,
    group_report_filename,
    is_report_ready,
    report_filename,
    read_file_from_mongo,
    save_file_to_mongo,
    upsert_report_metadata,
)
from app.application.services.application_store_service import (
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
from app.routes.interview_routes import finalize_partial_interview, select_report_application, with_public_interview_fields


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

    report_application = select_report_application(application)

    if not report_application or not is_report_ready(report_application):
        raise HTTPException(
            status_code=400,
            detail="Candidate report is available after a complete or partial interview attempt.",
        )

    pdf_bytes = generate_candidate_report_pdf(report_application)
    filename = report_filename(report_application)
    _store_report_pdf(pdf_bytes, filename, report_application, "candidate_report")
    return _pdf_response(pdf_bytes, filename)


@router.post("/reports")
def download_candidate_reports(payload: BulkReportRequest):
    applications = _resolve_report_applications(payload)

    if not applications:
        raise HTTPException(status_code=400, detail="No complete or partial candidate evaluations are available for report generation.")

    incomplete = [
        str(application.get("application_id") or application.get("_id") or "unknown")
        for application in applications
        if not is_report_ready(application)
    ]

    if incomplete:
        raise HTTPException(
            status_code=400,
            detail=f"Reports can be generated only for complete or partial interviews: {', '.join(incomplete)}",
        )

    pdf_bytes = generate_candidate_reports_pdf(applications)
    filename = group_report_filename()
    _store_report_pdf(pdf_bytes, filename, {"application_id": "", "job_id": payload.job_id}, "bulk_candidate_report")
    return _pdf_response(pdf_bytes, filename)


@router.delete("/applications/{application_id}")
def remove_application(application_id: str):
    if not delete_application(application_id):
        raise HTTPException(status_code=404, detail="Application not found")

    return {
        "success": True,
        "message": "Application and related MongoDB records deleted",
    }

@router.get("/applications/{application_id}/resume/download")
def download_application_resume(application_id: str):
    application = get_application_by_id(application_id)

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    stored_file = _resume_file_from_application(application)

    if not stored_file:
        raise HTTPException(status_code=404, detail="Resume file not found")

    return Response(
        content=stored_file["content"],
        media_type=stored_file.get("content_type") or "application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{application.get("file_name") or stored_file.get("filename") or "resume.pdf"}"'
        },
    )

@router.get("/applications/{application_id}/resume/view")
def view_application_resume(application_id: str):

    application = get_application_by_id(application_id)

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    stored_file = _resume_file_from_application(application)

    if not stored_file:
        raise HTTPException(status_code=404, detail="Resume file not found")

    pdf_bytes = stored_file["content"]

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
                report_application = select_report_application(_finalize_if_partial_or_quit(application))
                applications.append(report_application or _finalize_if_partial_or_quit(application))
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
        for application in (
            select_report_application(_finalize_if_partial_or_quit(application))
            for application in list_applications()
            if str(application.get("job_id") or "") == job_id
        )
        if application and is_report_ready(application)
    ]


def _finalize_if_partial_or_quit(application: dict) -> dict:
    application = with_public_interview_fields(application)
    status = str(application.get("interview_status") or application.get("interviewStatus") or "").lower()

    if status != "partial":
        return application

    application_id = str(application.get("application_id") or application.get("_id") or "")

    if not application_id:
        return application

    return with_public_interview_fields(finalize_partial_interview(application_id, status=status) or application)


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


def _resume_file_from_application(application: dict) -> dict | None:
    file_id = application.get("resumeFileId") or application.get("resume_file_id")
    file_path = str(application.get("file_path") or "")

    if not file_id and file_path.startswith("gridfs://"):
        file_id = file_path.replace("gridfs://", "", 1)

    return read_file_from_mongo(file_id) if file_id else None


def _store_report_pdf(pdf_bytes: bytes, filename: str, application: dict, report_type: str) -> None:
    file_id = save_file_to_mongo(
        pdf_bytes,
        filename=filename,
        content_type="application/pdf",
        metadata={
            "application_id": application.get("application_id"),
            "job_id": application.get("job_id") or application.get("jobId"),
            "report_type": report_type,
        },
    )
    report_id = f"{report_type}:{application.get('application_id') or application.get('job_id') or file_id}"
    upsert_report_metadata(
        report_id,
        {
            "reportId": report_id,
            "candidateId": application.get("application_id"),
            "application_id": application.get("application_id"),
            "jobId": application.get("job_id") or application.get("jobId"),
            "job_id": application.get("job_id") or application.get("jobId"),
            "reportType": report_type,
            "report_type": report_type,
            "reportFileId": file_id,
            "report_file_id": file_id,
            "metadata": {"filename": filename},
        },
    )
