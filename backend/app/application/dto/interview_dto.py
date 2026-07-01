from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InterviewConfigDTO:
    candidate_id: str
    question_source: str = "question_bank"
    number_of_questions: int = 0
    identity_config: dict = field(default_factory=dict)
