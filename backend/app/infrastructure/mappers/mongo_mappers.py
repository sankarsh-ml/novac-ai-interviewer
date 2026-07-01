from __future__ import annotations

from app.infrastructure.database.mongo_service import make_json_safe, public_document


def to_public_document(document: dict | None) -> dict | None:
    return public_document(document)


def to_mongo_document(data: dict) -> dict:
    return make_json_safe(data or {})
