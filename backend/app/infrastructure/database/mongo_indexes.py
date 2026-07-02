from __future__ import annotations

from app.utils.interview_tokens import (
    generate_interview_token,
    get_interview_link_token,
    interview_needs_token,
)


def ensure_indexes(db) -> None:
    cleanup_interview_link_tokens(db)
    db.jobs.create_index("jobId")
    db.jobs.create_index("id")
    db.candidates.create_index("jobId")
    db.candidates.create_index("job_id")
    db.candidates.create_index("candidateId")
    db.candidates.create_index("application_id", unique=True)
    db.candidates.create_index("email")
    db.question_bank.create_index("jobId")
    db.question_bank.create_index("job_id")
    question_indexes = db.question_bank.index_information()
    question_id_index = question_indexes.get("questionId_1")

    if question_id_index and question_id_index.get("unique"):
        db.question_bank.drop_index("questionId_1")

    db.question_bank.create_index("questionId")
    db.question_bank.create_index("question_id")
    db.interviews.create_index(
        [("interviewId", 1)],
        unique=True,
        partialFilterExpression={"interviewId": {"$type": "string"}},
    )
    db.interviews.create_index("candidateId")
    db.interviews.create_index("application_id")
    db.interviews.create_index("jobId")
    db.interviews.create_index(
        [("interviewLinkToken", 1)],
        unique=True,
        partialFilterExpression={"interviewLinkToken": {"$type": "string"}},
    )
    print("[MongoDB] Ensured interviewLinkToken unique partial index")
    db.interviews.create_index("status")
    db.interview_answers.create_index("interviewId")
    db.interview_answers.create_index("candidateId")
    db.interview_answers.create_index("application_id")
    db.identity_verifications.create_index("candidateId")
    db.identity_verifications.create_index("application_id")
    db.face_verifications.create_index("candidateId")
    db.face_verifications.create_index("application_id")
    db.reports.create_index("candidateId")
    db.reports.create_index("jobId")
    db.admin_users.create_index("username", unique=True)
    db.admin_users.create_index("adminId")


def cleanup_interview_link_tokens(db) -> None:
    _drop_unsafe_token_indexes(db)
    _drop_conflicting_interview_link_token_indexes(db)
    _drop_conflicting_interview_id_indexes(db)
    seen_tokens: set[str] = set()
    seen_interview_ids: set[str] = set()

    for interview in db.interviews.find({}).sort("_id", 1):
        updates: dict = {}
        unset_fields: dict = {}

        token = get_interview_link_token(interview)

        if token and token in seen_tokens:
            if interview_needs_token(interview):
                token = _fresh_unique_token(db, seen_tokens)
                updates["interviewLinkToken"] = token
            else:
                token = ""
                unset_fields["interviewLinkToken"] = ""
        elif token:
            updates["interviewLinkToken"] = token
            seen_tokens.add(token)
        elif interview_needs_token(interview):
            token = _fresh_unique_token(db, seen_tokens)
            updates["interviewLinkToken"] = token

        interview_id = str(interview.get("interviewId") or interview.get("interview_id") or "").strip()

        if interview_id and interview_id in seen_interview_ids:
            if interview_needs_token(interview):
                interview_id = _unique_interview_id(db, seen_interview_ids, updates.get("interviewLinkToken") or token)
                updates["interviewId"] = interview_id
            else:
                interview_id = ""
                unset_fields["interviewId"] = ""
        elif interview_id:
            seen_interview_ids.add(interview_id)
        elif interview_needs_token(interview):
            interview_id = _unique_interview_id(db, seen_interview_ids, updates.get("interviewLinkToken") or token)
            updates["interviewId"] = interview_id

        if interview_id:
            seen_interview_ids.add(interview_id)

        for field in ("token", "linkToken", "interview_token", "interviewLinkToken"):
            value = interview.get(field)

            if value is None or value == "":
                unset_fields[field] = ""

        for field in updates:
            unset_fields.pop(field, None)

        operation = {}

        if updates:
            operation["$set"] = updates

        if unset_fields:
            operation["$unset"] = unset_fields

        if operation:
            db.interviews.update_one({"_id": interview["_id"]}, operation)


def _drop_unsafe_token_indexes(db) -> None:
    for index in list(db.interviews.list_indexes()):
        index_name = index.get("name", "")
        key = list(index.get("key", {}).items())

        if key != [("token", 1)] or not index.get("unique"):
            continue

        partial_filter = index.get("partialFilterExpression")

        if partial_filter == {"token": {"$type": "string"}}:
            continue

        db.interviews.drop_index(index_name)
        print(f"[MongoDB] Dropped legacy token index {index_name}")


def _drop_conflicting_interview_link_token_indexes(db) -> None:
    expected_partial = {"interviewLinkToken": {"$type": "string"}}

    for index in list(db.interviews.list_indexes()):
        index_name = index.get("name", "")
        key = list(index.get("key", {}).items())

        if key != [("interviewLinkToken", 1)]:
            continue

        if index.get("unique") and index.get("partialFilterExpression") == expected_partial:
            continue

        db.interviews.drop_index(index_name)
        print(f"[MongoDB] Dropped conflicting interviewLinkToken index {index_name}")


def _drop_conflicting_interview_id_indexes(db) -> None:
    expected_partial = {"interviewId": {"$type": "string"}}

    for index in list(db.interviews.list_indexes()):
        index_name = index.get("name", "")
        key = list(index.get("key", {}).items())

        if key != [("interviewId", 1)]:
            continue

        if index.get("unique") and index.get("partialFilterExpression") == expected_partial:
            continue

        db.interviews.drop_index(index_name)
        print(f"[MongoDB] Dropped conflicting interviewId index {index_name}")


def _fresh_unique_token(db, seen_tokens: set[str]) -> str:
    while True:
        token = generate_interview_token()

        if token in seen_tokens:
            continue

        if db.interviews.find_one({"interviewLinkToken": token}, {"_id": 1}):
            continue

        seen_tokens.add(token)
        return token


def _fresh_unique_interview_id(db, seen_interview_ids: set[str]) -> str:
    while True:
        interview_id = generate_interview_token()

        if interview_id in seen_interview_ids:
            continue

        if db.interviews.find_one({"interviewId": interview_id}, {"_id": 1}):
            continue

        seen_interview_ids.add(interview_id)
        return interview_id


def _unique_interview_id(db, seen_interview_ids: set[str], preferred: str | None = None) -> str:
    candidate = str(preferred or "").strip()

    if (
        candidate
        and candidate not in seen_interview_ids
        and not db.interviews.find_one({"interviewId": candidate}, {"_id": 1})
    ):
        seen_interview_ids.add(candidate)
        return candidate

    return _fresh_unique_interview_id(db, seen_interview_ids)
