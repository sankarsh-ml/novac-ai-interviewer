from __future__ import annotations

from app.infrastructure.database.mongo_service import get_database


def upsert_report_metadata(report_id: str, document: dict) -> None:
    get_database().reports.update_one(
        {"reportId": report_id},
        {"$set": document},
        upsert=True,
    )
