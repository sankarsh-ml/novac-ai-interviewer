from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Question:
    question_id: str
    question: str
    expected_answer: str = "N/A"
    difficulty: str = "medium"
    area_of_interest: str = "General"
    tags: list[str] = field(default_factory=list)
