from __future__ import annotations

from app.application.services.answer_evaluation_service import evaluate_answer_with_qwen, normalize_score
from app.repositories import interview_repository


def upsert_interview_for_candidate(candidate_id: str, data: dict, insert_defaults: dict | None = None) -> None:
    interview_repository.upsert_interview_for_candidate(candidate_id, data, insert_defaults)


def get_link_by_token(token: str) -> dict | None:
    return interview_repository.get_link_by_token(token)


def mark_link_used(token: str) -> None:
    interview_repository.mark_link_used(token)

def delete_interview_for_candidate(candidate_id: str) -> None:
    interview_repository.delete_interview_for_candidate(candidate_id)