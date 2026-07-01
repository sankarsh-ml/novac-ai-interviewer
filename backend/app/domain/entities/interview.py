from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Interview:
    interview_id: str
    candidate_id: str
    job_id: str = ""
    status: str = "configured"
    questions: list[dict] = field(default_factory=list)
    identity_config: dict = field(default_factory=dict)
