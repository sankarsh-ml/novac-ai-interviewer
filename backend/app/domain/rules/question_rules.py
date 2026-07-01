from __future__ import annotations


def normalize_difficulty(value: str) -> str:
    difficulty = str(value or "medium").strip().lower()
    return difficulty if difficulty in {"easy", "medium", "hard"} else "medium"
