from __future__ import annotations

from app.domain.exceptions import ValidationError


def normalize_question_source(value: str) -> str:
    source = str(value or "question_bank").strip().lower()
    return "qwen_generated" if source in {"qwen", "qwen_generated", "ai", "ai_generated"} else "question_bank"


def validate_positive_question_count(count: int | None) -> None:
    if count is None or count <= 0:
        raise ValidationError("Number of questions must be greater than zero.")


def validate_difficulty_split(split: dict, total_questions: int) -> None:
    if sum(int(value or 0) for value in split.values()) <= 0:
        raise ValidationError("At least one Qwen-generated question is required.")

    if sum(int(value or 0) for value in split.values()) != total_questions:
        raise ValidationError("Difficulty split must add up to the total number of interview questions.")


def validate_configured_question_count(configured_count: int, requested_count: int) -> None:
    if requested_count <= 0 or configured_count != requested_count:
        raise ValidationError("Configured question count must exactly match number_of_questions before generating the link.")
