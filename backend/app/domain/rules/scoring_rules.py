from __future__ import annotations


def average_with_unanswered_zero(scores: list[float], total_questions: int) -> float:
    if total_questions <= 0:
        return 0.0

    normalized = [float(score or 0) for score in scores[:total_questions]]

    if len(normalized) < total_questions:
        normalized.extend([0.0] * (total_questions - len(normalized)))

    return round(sum(normalized) / total_questions, 1)
