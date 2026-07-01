from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Report:
    report_id: str
    candidate_id: str = ""
    job_id: str = ""
    report_type: str = ""
    file_id: str = ""
