from app.services.application_store_service import (
    accept_application,
    candidate_invite_state,
    clear_old_application_records,
    create_application,
    delete_application,
    find_application_by_invite_token,
    get_all_jobs,
    get_application_by_id,
    get_job_by_id,
    list_applications,
    save_job,
    update_application,
    update_ats_decision,
    update_candidate_step,
    update_interview_status,
    update_kyc_verification,
)


class MongoConnectionError(Exception):
    """Compatibility exception for old imports; MongoDB is no longer used."""


def save_resume_application(data: dict) -> str:
    return create_application(data)


def get_resume_application(application_id: str) -> dict | None:
    return get_application_by_id(application_id)


def update_ats_status(application_id: str, status: str) -> bool:
    return update_ats_decision(application_id, status)
