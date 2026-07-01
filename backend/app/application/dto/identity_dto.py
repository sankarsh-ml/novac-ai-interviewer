from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IdentityConfigDTO:
    require_government_id: bool = True
    face_verification_source: str = "government_id"
    resume_photo_available: bool = False
