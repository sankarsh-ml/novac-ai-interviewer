from __future__ import annotations

from app.application.services.resume_parser import (
    clean_text,
    extract_candidate_email,
    extract_candidate_name,
    extract_resume_photo,
    extract_sections,
    extract_text_from_pdf,
    normalize_text,
)
from app.infrastructure.storage.file_storage_service import save_file_to_mongo, save_path_to_mongo
