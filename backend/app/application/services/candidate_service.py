from __future__ import annotations

from app.application.services.application_store_service import (
    create_application,
    delete_application,
    delete_job_records,
    get_application_by_id,
    list_applications,
    quick_select_job_applications,
    update_application,
    update_ats_decision,
)


def get_candidate(application_id: str) -> dict | None:
    return get_application_by_id(application_id)


def save_candidate(data: dict) -> str:
    return create_application(data)


def list_candidates() -> list[dict]:
    return list_applications()


def update_candidate(application_id: str, updates: dict) -> bool:
    return update_application(application_id, updates)


def update_candidate_ats(application_id: str, decision: str) -> bool:
    return update_ats_decision(application_id, decision)


def quick_select(job_id: str, count: int) -> dict:
    return quick_select_job_applications(job_id, count)


def delete_candidate(application_id: str) -> bool:
    return delete_application(application_id)


def delete_all_records_for_job(job_id: str) -> int:
    return delete_job_records(job_id)
