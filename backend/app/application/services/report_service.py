from __future__ import annotations

from app.application.services.candidate_report_service import (
    generate_candidate_report_pdf,
    generate_candidate_reports_pdf,
    group_report_filename,
    is_report_ready,
    report_filename,
)
from app.infrastructure.storage.file_storage_service import read_file_from_mongo, save_file_to_mongo
from app.repositories import report_repository


def upsert_report_metadata(report_id: str, document: dict) -> None:
    report_repository.upsert_report_metadata(report_id, document)
