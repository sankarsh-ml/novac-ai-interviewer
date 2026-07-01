from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QuestionDTO:
    question_id: str
    question: str
    expected_answer: str = "N/A"
    difficulty: str = "medium"
