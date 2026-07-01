from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Candidate:
    application_id: str
    candidate_name: str = ""
    email: str = ""
    job_id: str = ""
    hr_decision: str = "pending"
    ats_status: str = "pending"
    metadata: dict = field(default_factory=dict)
