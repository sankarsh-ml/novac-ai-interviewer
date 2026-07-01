from __future__ import annotations

from app.application.services.kyc_service import verify_indian_id_for_application


def verify(application_id: str, id_file_path: str) -> dict:
    return verify_indian_id_for_application(application_id=application_id, id_file_path=id_file_path)
