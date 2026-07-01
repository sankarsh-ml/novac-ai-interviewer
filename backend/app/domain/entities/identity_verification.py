from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IdentityVerification:
    candidate_id: str
    source: str = "government_id"
    status: str = "not_started"
    score: float | None = None
