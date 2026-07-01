from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Answer:
    question_id: str
    candidate_answer: str = ""
    score: float = 0.0
    status: str = "submitted"
