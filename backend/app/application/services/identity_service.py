from __future__ import annotations

from app.application.services.identity_config_service import (
    build_identity_config,
    has_resume_photo,
    normalize_requested_identity_config,
    requires_government_id,
)
from app.application.services.kyc_service import verify_indian_id_for_application
from app.infrastructure.storage.file_storage_service import save_file_to_mongo, save_path_to_mongo
