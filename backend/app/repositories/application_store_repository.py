from __future__ import annotations

from datetime import datetime, timezone
import uuid

from app.infrastructure.storage.file_storage_service import delete_file_from_mongo
from app.infrastructure.database.mongo_service import get_database, make_json_safe, mongo_now, public_document
from app.utils.interview_tokens import get_interview_link_token, normalize_interview_token_fields


def create_application(data: dict) -> str:
    now = mongo_now()
    application_id = str(data.get("application_id") or data.get("candidateId") or uuid.uuid4())
    document = {
        **make_json_safe(data),
        "application_id": application_id,
        "candidateId": application_id,
        "candidate_id": application_id,
        "jobId": data.get("jobId") or data.get("job_id"),
        "job_id": data.get("job_id") or data.get("jobId"),
        "hr_decision": data.get("hr_decision", "pending"),
        "created_at": data.get("created_at") or now,
        "createdAt": data.get("createdAt") or now,
        "updated_at": now,
        "updatedAt": now,
    }

    get_database().candidates.insert_one(document)
    print(f"[Storage] Saved candidate to MongoDB candidateId={application_id}")
    return application_id


def get_application_by_id(application_id: str) -> dict | None:
    if not application_id:
        return None

    document = get_database().candidates.find_one(_application_filter(application_id))
    return public_document(document)


def update_application(application_id: str, updates: dict) -> bool:
    if not application_id:
        return False

    now = mongo_now()
    safe_updates = {
        **make_json_safe(updates),
        "updated_at": now,
        "updatedAt": now,
    }

    result = get_database().candidates.update_one(
        _application_filter(application_id),
        {"$set": safe_updates},
    )

    if result.matched_count:
        _mirror_related_records(application_id, safe_updates)

    if result.modified_count:
        print(f"[Storage] Saved candidate to MongoDB candidateId={application_id}")

    return result.matched_count > 0


def delete_application(application_id: str) -> bool:
    if not application_id:
        return False

    db = get_database()
    application = db.candidates.find_one(_application_filter(application_id))

    if not application:
        return False

    _delete_related_gridfs_files(application)
    _delete_gridfs_files_for_filters(_candidate_or_filters(application_id))
    db.candidates.delete_one(_application_filter(application_id))
    db.interviews.delete_many({"$or": _candidate_or_filters(application_id)})
    db.interview_answers.delete_many({"$or": _candidate_or_filters(application_id)})
    db.identity_verifications.delete_many({"$or": _candidate_or_filters(application_id)})
    db.face_verifications.delete_many({"$or": _candidate_or_filters(application_id)})
    db.reports.delete_many({"$or": _candidate_or_filters(application_id)})
    print(f"[Storage] Deleted related records for candidateId={application_id}")
    return True


def quick_select_job_applications(job_id: str, count: int) -> dict:
    if not job_id or count <= 0:
        return _quick_select_result(False, 0, 0, 0, [])

    db = get_database()
    applications = [public_document(item) for item in db.candidates.find(_job_filter(job_id))]
    applications = [item for item in applications if item]
    ranked_applications = sorted(applications, key=_application_rank_key, reverse=True)
    available = [item for item in ranked_applications if _is_available_for_quick_select(item)]

    if count > len(available):
        return {
            **_quick_select_result(False, 0, 0, len(available), ranked_applications),
            "message": f"Only {len(available)} candidate(s) available to select. Requested {count}.",
        }

    selected_ids = [item["application_id"] for item in available[:count]]
    now = mongo_now()

    if selected_ids:
        db.candidates.update_many(
            {"application_id": {"$in": selected_ids}},
            {"$set": {"hr_decision": "selected", "updated_at": now, "updatedAt": now}},
        )

    updated = [public_document(item) for item in db.candidates.find(_job_filter(job_id))]
    updated = sorted([item for item in updated if item], key=_application_rank_key, reverse=True)
    return _quick_select_result(True, len(selected_ids), len(selected_ids), len(available), updated)


def delete_job_records(job_id: str) -> int:
    if not job_id:
        return 0

    db = get_database()
    applications = [public_document(item) for item in db.candidates.find(_job_filter(job_id))]

    for application in applications:
        if application:
            _delete_related_gridfs_files(application)

    candidate_ids = [item.get("application_id") for item in applications if item and item.get("application_id")]
    related_filters = [_job_filter(job_id)]

    for candidate_id in candidate_ids:
        related_filters.extend(_candidate_or_filters(candidate_id))

    _delete_gridfs_files_for_filters(related_filters)
    db.candidates.delete_many(_job_filter(job_id))
    db.interviews.delete_many(_job_filter(job_id))
    db.interview_answers.delete_many(_job_filter(job_id))
    db.identity_verifications.delete_many(_job_filter(job_id))
    db.face_verifications.delete_many(_job_filter(job_id))
    db.reports.delete_many(_job_filter(job_id))

    if candidate_ids:
        for collection_name in ("interviews", "interview_answers", "identity_verifications", "face_verifications", "reports"):
            db[collection_name].delete_many({"candidateId": {"$in": candidate_ids}})
            db[collection_name].delete_many({"application_id": {"$in": candidate_ids}})

    print(f"[Storage] Deleted all job records jobId={job_id}")
    return len(applications)


def list_applications() -> list[dict]:
    documents = get_database().candidates.find({}).sort("created_at", -1)
    return [item for item in (public_document(document) for document in documents) if item]


def update_ats_decision(application_id: str, decision: str) -> bool:
    normalized_decision = str(decision or "").lower().strip()
    return update_application(
        application_id,
        {
            "ats_status": normalized_decision,
            "ats_decision": normalized_decision,
        },
    )


def update_kyc_verification(application_id: str, data: dict) -> bool:
    db = get_database()
    application = get_application_by_id(application_id) or {}
    now = mongo_now()
    verification_id = str(data.get("verificationId") or data.get("verification_id") or uuid.uuid4())
    document = {
        **make_json_safe(data),
        "verificationId": verification_id,
        "verification_id": verification_id,
        "candidateId": application_id,
        "application_id": application_id,
        "jobId": application.get("jobId") or application.get("job_id"),
        "job_id": application.get("job_id") or application.get("jobId"),
        "createdAt": data.get("createdAt") or now,
        "created_at": data.get("created_at") or now,
        "updatedAt": now,
        "updated_at": now,
    }
    db.identity_verifications.update_one(
        {"candidateId": application_id},
        {"$set": document},
        upsert=True,
    )

    updates = {
        "aadhaar_verification": data,
        "kyc_verification": data,
        "identityVerification": data.get("identityVerification") or data.get("identity_verification") or data,
        "identity_verification": data.get("identityVerification") or data.get("identity_verification") or data,
    }

    aadhaar_photo_path = data.get("aadhaar_photo_path") if isinstance(data, dict) else None
    if aadhaar_photo_path:
        updates["aadhaar_photo_path"] = aadhaar_photo_path
        updates["aadhaar_face_image_path"] = data.get("aadhaar_face_image_path") or aadhaar_photo_path

    extracted_name = data.get("extracted_name") if isinstance(data, dict) else None
    if extracted_name:
        updates["aadhaar_extracted_name"] = extracted_name

    return update_application(application_id, updates)


def update_interview_status(application_id: str, data: dict) -> bool:
    return update_application(application_id, {"interview_status": data})


def save_job(job_data: dict) -> str:
    now = mongo_now()
    job_id = str(job_data.get("id") or job_data.get("jobId") or uuid.uuid4())
    document = {
        **make_json_safe(job_data),
        "id": job_id,
        "jobId": job_id,
        "job_id": job_id,
        "requiredSkills": job_data.get("requiredSkills") or job_data.get("required_skills") or [],
        "required_skills": job_data.get("required_skills") or job_data.get("requiredSkills") or [],
        "createdAt": job_data.get("createdAt") or now,
        "created_at": job_data.get("created_at") or now,
        "updatedAt": now,
        "updated_at": now,
        "status": job_data.get("status") or "active",
    }
    get_database().jobs.insert_one(document)
    print(f"[Storage] Saved job to MongoDB jobId={job_id}")
    return job_id


def get_all_jobs() -> list[dict]:
    documents = get_database().jobs.find({}).sort("created_at", -1)
    return [item for item in (public_document(document) for document in documents) if item]


def get_job_by_id(job_id: str) -> dict | None:
    if not job_id:
        return None

    document = get_database().jobs.find_one(_job_identity_filter(job_id))
    return public_document(document)


def delete_job(job_id: str) -> bool:
    if not job_id:
        return False

    db = get_database()
    job = db.jobs.find_one(_job_identity_filter(job_id))

    if not job:
        return False

    delete_job_records(job_id)
    db.jobs.delete_one(_job_identity_filter(job_id))
    return True


def _application_filter(application_id: str) -> dict:
    return {
        "$or": [
            {"application_id": str(application_id)},
            {"candidateId": str(application_id)},
            {"candidate_id": str(application_id)},
        ]
    }


def _candidate_or_filters(application_id: str) -> list[dict]:
    return [
        {"application_id": str(application_id)},
        {"candidateId": str(application_id)},
        {"candidate_id": str(application_id)},
    ]


def _job_filter(job_id: str) -> dict:
    return {
        "$or": [
            {"job_id": str(job_id)},
            {"jobId": str(job_id)},
            {"id": str(job_id)},
        ]
    }


def _job_identity_filter(job_id: str) -> dict:
    return {
        "$or": [
            {"id": str(job_id)},
            {"jobId": str(job_id)},
            {"job_id": str(job_id)},
        ]
    }


def _quick_select_result(success: bool, selected_count: int, updated_count: int, available_count: int, applications: list[dict]) -> dict:
    return {
        "success": success,
        "selected_count": selected_count,
        "updated_count": updated_count,
        "available_count": available_count,
        "applications": applications,
    }


def _is_available_for_quick_select(application: dict) -> bool:
    decision = str(application.get("hr_decision") or "").lower().strip()
    return decision not in {"selected", "rejected"}


def _application_rank_key(application: dict) -> float:
    for key in ("ats_score", "rank_score", "score"):
        value = application.get(key)

        if value is None and isinstance(application.get("ats_result"), dict):
            value = application["ats_result"].get(key)

        try:
            return float(value)
        except (TypeError, ValueError):
            continue

    return 0.0


def _delete_related_gridfs_files(document: dict) -> None:
    for key in (
        "resumeFileId",
        "resume_file_id",
        "resumePhotoFileId",
        "resume_photo_file_id",
        "governmentIdFileId",
        "government_id_file_id",
        "governmentIdPhotoFileId",
        "government_id_photo_file_id",
        "reportFileId",
        "report_file_id",
        "documentFileId",
        "document_file_id",
        "photoFileId",
        "photo_file_id",
    ):
        delete_file_from_mongo(document.get(key))


def _delete_gridfs_files_for_filters(filters: list[dict]) -> None:
    db = get_database()

    for collection_name in ("interviews", "interview_answers", "identity_verifications", "face_verifications", "reports"):
        for document in db[collection_name].find({"$or": filters} if len(filters) > 1 else filters[0]):
            _delete_related_gridfs_files(public_document(document) or {})


def _mirror_related_records(application_id: str, updates: dict) -> None:
    db = get_database()
    application = get_application_by_id(application_id) or {}
    job_id = application.get("jobId") or application.get("job_id")
    now = mongo_now()

    if any(
        key in updates
        for key in (
            "interview_config",
            "interview_questions",
            "interviewQuestions",
            "interview_token",
            "interview_link",
            "finalQuestions",
            "generatedQuestions",
            "question_source",
            "questionSource",
            "interview_status",
        )
    ):
        existing_token = get_interview_link_token(application)
        interview_id = str(application.get("interviewId") or application.get("interview_id") or existing_token or application_id)
        config = application.get("interview_config") if isinstance(application.get("interview_config"), dict) else {}
        question_payload = application.get("interview_questions") if isinstance(application.get("interview_questions"), dict) else {}
        final_questions = (
            application.get("finalQuestions")
            or application.get("final_questions")
            or question_payload.get("questions")
            or []
        )
        interview_values, unset_fields = normalize_interview_token_fields(
            {
                "interviewId": interview_id,
                "candidateId": application_id,
                "application_id": application_id,
                "jobId": job_id,
                "job_id": job_id,
                "interviewLinkToken": existing_token,
                "questionSource": application.get("questionSource") or application.get("question_source") or config.get("question_source"),
                "question_source": application.get("question_source") or application.get("questionSource") or config.get("question_source"),
                "selectedQuestionIds": application.get("selectedQuestionIds") or config.get("selected_question_ids") or [],
                "selected_question_ids": application.get("selected_question_ids") or config.get("selected_question_ids") or [],
                "generatedQuestions": application.get("generatedQuestions") or question_payload.get("generatedQuestions") or [],
                "generated_questions": application.get("generated_questions") or question_payload.get("generated_questions") or [],
                "difficultySplit": application.get("difficultySplit") or config.get("difficulty_split") or {},
                "difficulty_split": application.get("difficulty_split") or config.get("difficulty_split") or {},
                "questionCount": application.get("total_questions") or config.get("number_of_questions"),
                "question_count": application.get("total_questions") or config.get("number_of_questions"),
                "finalQuestions": final_questions,
                "final_questions": final_questions,
                "status": _interview_collection_status(application),
                "startedAt": application.get("interview_started_at"),
                "completedAt": application.get("interview_completed_at") or application.get("completedAt"),
                "updatedAt": now,
            },
            generate_missing=True,
        )
        update_document = {
            "$set": interview_values,
            "$setOnInsert": {"createdAt": now},
        }

        if unset_fields:
            update_document["$unset"] = unset_fields

        db.interviews.update_one(
            {"candidateId": application_id, "interviewId": interview_id},
            update_document,
            upsert=True,
        )
        print(f"[Storage] Saved interview to MongoDB interviewId={interview_id}")

    if "interview_answers" in updates and isinstance(application.get("interview_answers"), dict):
        interview_id = str(application.get("interviewId") or application.get("interview_id") or get_interview_link_token(application) or application_id)

        for question_id, answer in application["interview_answers"].items():
            if not isinstance(answer, dict):
                continue

            question_index = answer.get("question_index") or answer.get("questionIndex") or 0
            attempt_number = answer.get("attemptNumber") or answer.get("attempt_number") or application.get("attemptNumber") or application.get("attempt_number") or 1
            answer_id = f"{interview_id}:{attempt_number}:{question_id}"
            db.interview_answers.update_one(
                {"answerId": answer_id, "archived": {"$ne": True}},
                {
                    "$set": {
                        **make_json_safe(answer),
                        "answerId": answer_id,
                        "answer_id": answer_id,
                        "interviewId": interview_id,
                        "candidateId": application_id,
                        "application_id": application_id,
                        "jobId": job_id,
                        "job_id": job_id,
                        "attemptNumber": attempt_number,
                        "attempt_number": attempt_number,
                        "archived": False,
                        "questionIndex": question_index,
                        "question_index": question_index,
                        "question": answer.get("question"),
                        "expectedAnswer": answer.get("expectedAnswer") or answer.get("expected_answer"),
                        "candidateAnswer": answer.get("candidate_answer") or answer.get("answerText") or answer.get("answer_text"),
                        "evaluation": answer.get("evaluation") or answer.get("feedback"),
                        "score": answer.get("score") or answer.get("finalScore") or answer.get("final_score"),
                        "answeredAt": answer.get("submittedAt") or answer.get("submitted_at"),
                        "updatedAt": now,
                    },
                    "$setOnInsert": {"createdAt": now},
                },
                upsert=True,
            )
            print(f"[Storage] Saved answer to MongoDB interviewId={interview_id} questionIndex={question_index}")

    identity = updates.get("identityVerification") or updates.get("identity_verification")

    if isinstance(identity, dict):
        db.identity_verifications.update_one(
            {"candidateId": application_id},
            {
                "$set": {
                    **make_json_safe(identity),
                    "candidateId": application_id,
                    "application_id": application_id,
                    "jobId": job_id,
                    "job_id": job_id,
                    "updatedAt": now,
                    "updated_at": now,
                },
                "$setOnInsert": {"createdAt": now, "created_at": now},
            },
            upsert=True,
        )


def _interview_collection_status(application: dict) -> str:
    status = str(application.get("interview_status") or application.get("interviewStatus") or "").lower()

    if status in {"complete", "completed"}:
        return "complete"

    if status in {"partial", "quit", "interrupted"}:
        return "partial"

    return "not_started"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
