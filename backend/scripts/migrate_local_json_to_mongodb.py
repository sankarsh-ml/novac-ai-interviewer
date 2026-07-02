from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.application.services.admin_service import create_or_update_admin
from app.infrastructure.database.mongo_service import get_database, make_json_safe, mongo_now
from app.utils.interview_tokens import get_interview_link_token


APP_STORAGE_DIR = BACKEND_DIR / "app" / "storage"


def main() -> None:
    db = get_database()
    summary = {
        "jobs": migrate_jobs(db),
        "candidates": migrate_candidates(db),
        "question_bank": migrate_question_banks(db),
        "interviews": migrate_interview_links(db),
        "admin_users": migrate_admin_users(),
    }

    print("Migration summary:")
    for key, count in summary.items():
        print(f"- {key}: {count}")

    print("Migration complete. You can archive old local JSON files manually.")


def migrate_jobs(db) -> int:
    rows = _read_json_list(APP_STORAGE_DIR / "jobs.json")
    count = 0

    for row in rows:
        job_id = str(row.get("id") or row.get("jobId") or "")

        if not job_id:
            continue

        now = mongo_now()
        document = {
            **make_json_safe(row),
            "id": job_id,
            "jobId": job_id,
            "job_id": job_id,
            "requiredSkills": row.get("requiredSkills") or row.get("required_skills") or [],
            "required_skills": row.get("required_skills") or row.get("requiredSkills") or [],
            "updatedAt": now,
            "updated_at": now,
        }
        db.jobs.update_one({"id": job_id}, {"$set": document, "$setOnInsert": {"createdAt": now}}, upsert=True)
        count += 1

    return count


def migrate_candidates(db) -> int:
    rows = _read_json_list(APP_STORAGE_DIR / "applications.json")
    count = 0

    for row in rows:
        candidate_id = str(row.get("application_id") or row.get("candidateId") or row.get("_id") or "")

        if not candidate_id:
            continue

        now = mongo_now()
        document = {
            **make_json_safe(row),
            "application_id": candidate_id,
            "candidateId": candidate_id,
            "candidate_id": candidate_id,
            "jobId": row.get("jobId") or row.get("job_id"),
            "job_id": row.get("job_id") or row.get("jobId"),
            "updatedAt": now,
            "updated_at": now,
        }
        db.candidates.update_one(
            {"application_id": candidate_id},
            {"$set": document, "$setOnInsert": {"createdAt": row.get("createdAt") or row.get("created_at") or now}},
            upsert=True,
        )
        _migrate_embedded_records(db, document)
        count += 1

    return count


def migrate_question_banks(db) -> int:
    question_bank_dir = APP_STORAGE_DIR / "question_banks"
    count = 0

    if not question_bank_dir.exists():
        return count

    for file_path in question_bank_dir.glob("*.json"):
        data = _read_json_object(file_path)
        job_id = str(data.get("job_id") or file_path.stem)
        questions = data.get("questions") if isinstance(data.get("questions"), list) else []

        for question in questions:
            question_id = str(question.get("question_id") or question.get("id") or question.get("_id") or "")

            if not question_id:
                continue

            document = {
                **make_json_safe(question),
                "questionId": question_id,
                "question_id": question_id,
                "id": question_id,
                "jobId": job_id,
                "job_id": job_id,
                "updatedAt": mongo_now(),
            }
            db.question_bank.update_one(
                {"questionId": question_id, "jobId": job_id},
                {"$set": document, "$setOnInsert": {"createdAt": question.get("createdAt") or question.get("created_at") or mongo_now()}},
                upsert=True,
            )
            count += 1

    return count


def migrate_interview_links(db) -> int:
    link_dir = APP_STORAGE_DIR / "interview_links"
    count = 0

    if not link_dir.exists():
        return count

    for file_path in link_dir.glob("*.json"):
        data = _read_json_object(file_path)
        token = str(get_interview_link_token(data) or file_path.stem)
        candidate_id = str(data.get("application_id") or data.get("candidateId") or "")

        if not token:
            continue

        document = {
            **make_json_safe(data),
            "interviewId": data.get("interviewId") or token,
            "interviewLinkToken": token,
            "candidateId": candidate_id,
            "application_id": candidate_id,
            "updatedAt": mongo_now(),
        }
        db.interviews.update_one(
            {"interviewLinkToken": token},
            {"$set": document, "$setOnInsert": {"createdAt": mongo_now()}},
            upsert=True,
        )
        count += 1

    return count


def migrate_admin_users() -> int:
    credential_file = APP_STORAGE_DIR / "admin_credentials.json"
    data = _read_json_object(credential_file)
    admins = []

    if isinstance(data.get("admins"), list):
        admins = data["admins"]
    elif data.get("username") and data.get("password"):
        admins = [data]

    count = 0

    for admin in admins:
        if not isinstance(admin, dict):
            continue

        username = str(admin.get("username") or "").strip()
        password = str(admin.get("password") or "")

        if not username or not password:
            continue

        if create_or_update_admin(username, password, role=str(admin.get("role") or "admin")):
            print(f"Migrated admin user: {username}")
            count += 1

    return count


def _migrate_embedded_records(db, candidate: dict) -> None:
    candidate_id = candidate.get("application_id")
    job_id = candidate.get("job_id") or candidate.get("jobId")
    identity = candidate.get("identityVerification") or candidate.get("identity_verification") or candidate.get("kyc_verification")

    if isinstance(identity, dict):
        db.identity_verifications.update_one(
            {"candidateId": candidate_id},
            {
                "$set": {
                    **make_json_safe(identity),
                    "candidateId": candidate_id,
                    "application_id": candidate_id,
                    "jobId": job_id,
                    "job_id": job_id,
                    "updatedAt": mongo_now(),
                },
                "$setOnInsert": {"createdAt": mongo_now()},
            },
            upsert=True,
        )

    answers = candidate.get("interview_answers")

    if isinstance(answers, dict):
        interview_id = str(candidate.get("interview_token") or candidate_id)

        for question_id, answer in answers.items():
            if not isinstance(answer, dict):
                continue

            answer_id = f"{interview_id}:{question_id}"
            db.interview_answers.update_one(
                {"answerId": answer_id},
                {
                    "$set": {
                        **make_json_safe(answer),
                        "answerId": answer_id,
                        "interviewId": interview_id,
                        "candidateId": candidate_id,
                        "jobId": job_id,
                        "updatedAt": mongo_now(),
                    },
                    "$setOnInsert": {"createdAt": mongo_now()},
                },
                upsert=True,
            )


def _read_json_list(file_path: Path) -> list[dict]:
    data = _read_json_object(file_path, default=[])
    return data if isinstance(data, list) else []


def _read_json_object(file_path: Path, default=None):
    if default is None:
        default = {}

    if not file_path.exists():
        return default

    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as error:
        print(f"Skipped unreadable JSON file {file_path}: {error}")
        return default


if __name__ == "__main__":
    main()
