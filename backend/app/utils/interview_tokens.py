from __future__ import annotations

import secrets
from typing import Any

CANONICAL_INTERVIEW_TOKEN_FIELD = "interviewLinkToken"
LEGACY_INTERVIEW_TOKEN_FIELDS = ("token", "linkToken", "interview_token")
INTERVIEW_TOKEN_FIELDS = (CANONICAL_INTERVIEW_TOKEN_FIELD, *LEGACY_INTERVIEW_TOKEN_FIELDS)
ACTIVE_INTERVIEW_STATUSES = {
    "configured",
    "not_started",
    "link_generated",
    "in_progress",
    "partial",
    "abandoned",
}


def generate_interview_token() -> str:
    return secrets.token_urlsafe(32)


def get_interview_link_token(data: dict[str, Any] | None) -> str:
    if not isinstance(data, dict):
        return ""

    for field in INTERVIEW_TOKEN_FIELDS:
        value = data.get(field)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def interview_needs_token(data: dict[str, Any] | None) -> bool:
    if not isinstance(data, dict):
        return False

    status = str(
        data.get("status")
        or data.get("interview_status")
        or data.get("interviewStatus")
        or ""
    ).strip().lower()
    return status in ACTIVE_INTERVIEW_STATUSES


def normalize_interview_token_fields(
    data: dict[str, Any],
    *,
    generate_missing: bool = False,
    keep_legacy_strings: bool = False,
) -> tuple[dict[str, Any], dict[str, str]]:
    normalized = dict(data or {})
    token = get_interview_link_token(normalized)

    if token:
        normalized[CANONICAL_INTERVIEW_TOKEN_FIELD] = token
    elif generate_missing:
        token = generate_interview_token()
        normalized[CANONICAL_INTERVIEW_TOKEN_FIELD] = token

    unset_fields: dict[str, str] = {}

    for field in LEGACY_INTERVIEW_TOKEN_FIELDS:
        value = normalized.get(field)

        if value is None or value == "":
            normalized.pop(field, None)
            unset_fields[field] = ""
        elif not keep_legacy_strings:
            normalized.pop(field, None)

    if normalized.get(CANONICAL_INTERVIEW_TOKEN_FIELD) is None or normalized.get(CANONICAL_INTERVIEW_TOKEN_FIELD) == "":
        normalized.pop(CANONICAL_INTERVIEW_TOKEN_FIELD, None)
        unset_fields[CANONICAL_INTERVIEW_TOKEN_FIELD] = ""

    return normalized, unset_fields
