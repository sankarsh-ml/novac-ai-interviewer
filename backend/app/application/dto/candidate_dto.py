from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CandidateSummaryDTO:
    application_id: str
    candidate_name: str = ""
    email: str = ""
    job_id: str = ""
