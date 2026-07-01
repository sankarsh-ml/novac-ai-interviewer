from __future__ import annotations

from app.infrastructure.database.mongo_service import get_database


def upsert_answer(filter_query: dict, document: dict) -> None:
    get_database().interview_answers.update_one(filter_query, {"$set": document}, upsert=True)


def delete_many(filter_query: dict) -> int:
    return get_database().interview_answers.delete_many(filter_query).deleted_count
