from __future__ import annotations

from app.repositories import application_store_repository


class MongoConnectionError(Exception):
    pass


def create_application(data: dict) -> str:
    return application_store_repository.create_application(data)


def get_application_by_id(application_id: str) -> dict | None:
    return application_store_repository.get_application_by_id(application_id)


def update_application(application_id: str, updates: dict) -> bool:
    return application_store_repository.update_application(application_id, updates)


def delete_application(application_id: str) -> bool:
    return application_store_repository.delete_application(application_id)


def quick_select_job_applications(job_id: str, count: int) -> dict:
    return application_store_repository.quick_select_job_applications(job_id, count)


def delete_job_records(job_id: str) -> int:
    return application_store_repository.delete_job_records(job_id)


def list_applications() -> list[dict]:
    return application_store_repository.list_applications()


def update_ats_decision(application_id: str, decision: str) -> bool:
    return application_store_repository.update_ats_decision(application_id, decision)


def update_kyc_verification(application_id: str, data: dict) -> bool:
    return application_store_repository.update_kyc_verification(application_id, data)


def update_interview_status(application_id: str, data: dict) -> bool:
    return application_store_repository.update_interview_status(application_id, data)


def save_job(job_data: dict) -> str:
    return application_store_repository.save_job(job_data)


def get_all_jobs() -> list[dict]:
    return application_store_repository.get_all_jobs()


def get_job_by_id(job_id: str) -> dict | None:
    return application_store_repository.get_job_by_id(job_id)


def delete_job(job_id: str) -> bool:
    return application_store_repository.delete_job(job_id)


def save_resume_application(data: dict) -> str:
    return create_application(data)


def get_resume_application(application_id: str) -> dict | None:
    return get_application_by_id(application_id)


def update_ats_status(application_id: str, status: str) -> bool:
    return update_ats_decision(application_id, status)
