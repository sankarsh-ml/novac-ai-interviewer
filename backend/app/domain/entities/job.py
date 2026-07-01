from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Job:
    job_id: str
    title: str = ""
    required_skills: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
