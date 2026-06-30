from app.services.application_store_service import (
    create_application,
    delete_application,
    delete_job_records,
    get_all_jobs,
    get_application_by_id,
    get_job_by_id,
    list_applications,
    quick_select_job_applications,
    save_job,
    update_application,
    update_ats_decision,
    update_interview_status,
    update_kyc_verification,
    delete_job,
)


class MongoConnectionError(Exception):
    """Compatibility exception for old imports; MongoDB is no longer used."""


def save_resume_application(data: dict) -> str:
    return create_application(data)


def get_resume_application(application_id: str) -> dict | None:
    return get_application_by_id(application_id)


def update_ats_status(application_id: str, status: str) -> bool:
    return update_ats_decision(application_id, status)
