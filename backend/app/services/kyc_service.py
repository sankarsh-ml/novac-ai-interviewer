from datetime import datetime, timezone
from difflib import SequenceMatcher
import re

from app.services.db_service import (
    MongoConnectionError,
    get_resume_application,
    update_kyc_verification,
)
from app.services.face_match_service import compare_faces
from app.services.id_model_service import (
    extract_aadhaar_fields,
    extract_aadhaar_photo,
    is_aadhaar_card,
)


NAME_MATCH_THRESHOLD = 0.70


def normalize_name(name: str) -> str:
    name = re.sub(r"[^a-zA-Z ]", " ", name or "")
    name = re.sub(r"\s+", " ", name)
    return name.strip().lower()


def _name_tokens(name: str) -> list[str]:
    normalized = normalize_name(name)
    return [token for token in normalized.split() if token]


def _token_initial_match_score(name1: str, name2: str) -> float:
    """
    Handles cases like:
    Resume:  Sankarsh P
    Aadhaar: Sankarsh Ponnath
    """
    tokens1 = _name_tokens(name1)
    tokens2 = _name_tokens(name2)

    if not tokens1 or not tokens2:
        return 0.0

    shorter = tokens1 if len(tokens1) <= len(tokens2) else tokens2
    longer = tokens2 if len(tokens1) <= len(tokens2) else tokens1

    matched = 0

    for small_token in shorter:
        found = False

        for big_token in longer:
            if small_token == big_token:
                found = True
                break

            if len(small_token) == 1 and big_token.startswith(small_token):
                found = True
                break

            if len(big_token) == 1 and small_token.startswith(big_token):
                found = True
                break

        if found:
            matched += 1

    return round(matched / len(shorter), 4)


def calculate_name_similarity(name1: str, name2: str) -> float:
    normalized_name1 = normalize_name(name1)
    normalized_name2 = normalize_name(name2)

    if not normalized_name1 or not normalized_name2:
        return 0.0

    sequence_score = SequenceMatcher(None, normalized_name1, normalized_name2).ratio()
    token_score = _token_initial_match_score(normalized_name1, normalized_name2)

    return round(max(sequence_score, token_score), 4)


def mask_aadhaar_number(number: str) -> str:
    digits = re.sub(r"\D", "", number or "")

    if len(digits) < 4:
        return ""

    return f"XXXX XXXX {digits[-4:]}"


def _safe_get_nested(mapping: dict, keys: list[str], default=""):
    current = mapping

    for key in keys:
        if not isinstance(current, dict):
            return default

        current = current.get(key)

    return current if current is not None else default


def _extract_resume_name(application: dict) -> str:
    resume = application.get("resume", {})

    candidates = [
        resume.get("candidate_name", ""),
        application.get("candidate_name", ""),
        _safe_get_nested(resume, ["ats_ready_data", "candidate_name"], ""),
        _safe_get_nested(resume, ["ats_ready_data", "personal_info", "name"], ""),
        _safe_get_nested(
            resume,
            ["ats_ready_data", "sections_detected", "personal_info", "name"],
            "",
        ),
    ]

    for candidate in candidates:
        candidate = str(candidate or "").strip()

        if candidate:
            return candidate

    extracted_text = resume.get("extracted_text", "")

    for line in extracted_text.splitlines():
        line = line.strip()

        if not line:
            continue

        lower = line.lower()

        if any(bad in lower for bad in ["email", "phone", "linkedin", "github", "@"]):
            continue

        if re.search(r"[a-zA-Z]", line) and not re.search(r"\d", line):
            return line

    return ""


def _extract_aadhaar_name(aadhaar_fields: dict | None) -> str:
    aadhaar_fields = aadhaar_fields or {}

    possible_names = [
        aadhaar_fields.get("name", ""),
        aadhaar_fields.get("extracted_name", ""),
        aadhaar_fields.get("full_name", ""),
        aadhaar_fields.get("aadhaar_name", ""),
        aadhaar_fields.get("applicant_name", ""),
        aadhaar_fields.get("holder_name", ""),
    ]

    for name in possible_names:
        name = str(name or "").strip()

        if name:
            return name

    return ""


def _get_masked_aadhaar_number(aadhaar_fields: dict | None) -> str:
    aadhaar_fields = aadhaar_fields or {}

    masked = aadhaar_fields.get("masked_aadhaar_number", "")

    if masked:
        return masked

    return mask_aadhaar_number(aadhaar_fields.get("aadhaar_number", ""))


def _get_aadhaar_photo_path(aadhaar_photo: dict | None) -> str:
    aadhaar_photo = aadhaar_photo or {}

    return (
        aadhaar_photo.get("path")
        or aadhaar_photo.get("photo_path")
        or ""
    )


def _get_photo_match_result(resume: dict, aadhaar_photo: dict) -> dict:
    resume_photo_path = resume.get("resume_photo_path")
    aadhaar_photo_path = _get_aadhaar_photo_path(aadhaar_photo)

    if not resume_photo_path:
        return {
            "status": "skipped_no_resume_photo",
            "score": None,
            "message": "No resume photo found. Aadhaar photo stored for future live validation.",
        }

    if not aadhaar_photo_path:
        return {
            "status": "skipped_no_aadhaar_photo",
            "score": None,
            "message": "Aadhaar photo could not be extracted.",
        }

    try:
        return compare_faces(resume_photo_path, aadhaar_photo_path)
    except Exception as error:
        return {
            "status": "unavailable",
            "score": None,
            "message": f"Face matching unavailable: {str(error)}",
        }


def _safe_update_kyc(application_id: str, verification_result: dict):
    try:
        update_kyc_verification(application_id, verification_result)
    except MongoConnectionError:
        raise
    except Exception as error:
        print("KYC DB update failed:", error)


def verify_aadhaar_for_application(application_id: str, aadhaar_file_path: str) -> dict:
    application = get_resume_application(application_id)

    if not application:
        return {
            "success": False,
            "status_code": 404,
            "message": "Resume application not found",
            "data": {},
        }

    if application.get("ats_status") != "passed" and application.get("status") != "accepted":
        return {
            "success": False,
            "status_code": 403,
            "message": "Aadhaar verification is allowed only after ATS pass or HR acceptance.",
            "data": {},
        }

    print("\n========== KYC START ==========")
    print("APPLICATION ID:", application_id)
    print("AADHAAR FILE:", aadhaar_file_path)

    aadhaar_detection = is_aadhaar_card(aadhaar_file_path)
    print("AADHAAR DETECTION:", aadhaar_detection)

    if not aadhaar_detection.get("is_aadhaar"):
        if not aadhaar_detection.get("success", False):
            return _failure(
                message=aadhaar_detection.get("message") or "Indian ID validator failed to load.",
                status_code=500,
                application_id=application_id,
                application=application,
                aadhaar_detection=aadhaar_detection,
                next_step="retry",
            )

        return _failure(
            message="No valid Aadhaar detected. Please upload a clear Aadhaar card image or PDF.",
            status_code=400,
            application_id=application_id,
            application=application,
            aadhaar_detection=aadhaar_detection,
            next_step="recapture",
        )

    aadhaar_fields = extract_aadhaar_fields(aadhaar_file_path)
    print("AADHAAR FIELDS:", aadhaar_fields)

    aadhaar_name = _extract_aadhaar_name(aadhaar_fields)
    print("AADHAAR NAME:", aadhaar_name)

    if not aadhaar_name:
        return _failure(
            message="Aadhaar was detected, but name could not be extracted. Please upload a clearer Aadhaar image or PDF.",
            status_code=400,
            application_id=application_id,
            application=application,
            aadhaar_detection=aadhaar_detection,
            aadhaar_fields=aadhaar_fields,
            next_step="recapture",
        )

    resume = application.get("resume", {})
    resume_name = _extract_resume_name(application)
    print("RESUME NAME:", resume_name)

    if not resume_name:
        return _failure(
            message="Resume name could not be extracted.",
            status_code=400,
            application_id=application_id,
            application=application,
            aadhaar_detection=aadhaar_detection,
            aadhaar_fields=aadhaar_fields,
            next_step="stop",
        )

    name_match_score = calculate_name_similarity(resume_name, aadhaar_name)
    name_match_passed = name_match_score >= NAME_MATCH_THRESHOLD

    print("NAME MATCH SCORE:", name_match_score)
    print("NAME MATCH PASSED:", name_match_passed)

    aadhaar_photo = extract_aadhaar_photo(aadhaar_file_path)
    print("AADHAAR PHOTO:", aadhaar_photo)

    photo_match = _get_photo_match_result(resume, aadhaar_photo)
    print("PHOTO MATCH:", photo_match)

    verification_status = "passed" if name_match_passed else "failed"

    masked_aadhaar_number = _get_masked_aadhaar_number(aadhaar_fields)
    aadhaar_photo_path = _get_aadhaar_photo_path(aadhaar_photo)

    verification_result = {
        "verification_status": verification_status,
        "aadhaar_detected": True,
        "aadhaar_confidence": aadhaar_detection.get("confidence"),
        "extracted_name": aadhaar_name,
        "masked_aadhaar_number": masked_aadhaar_number,
        "dob": aadhaar_fields.get("dob", ""),
        "gender": aadhaar_fields.get("gender", ""),
        "aadhaar_photo_path": aadhaar_photo_path,
        "name_match_score": name_match_score,
        "name_match_passed": name_match_passed,
        "photo_match": photo_match,
        "updated_at": datetime.now(timezone.utc),
    }

    _safe_update_kyc(application_id, verification_result)

    if not name_match_passed:
        return {
            "success": False,
            "status_code": 400,
            "message": "Aadhaar name does not match resume name sufficiently.",
            "data": {
                "resume_name": resume_name,
                "aadhaar_name": aadhaar_name,
                "name_match_score": name_match_score,
                "name_match_passed": False,
                "next_step": "recapture",
            },
        }

    return {
        "success": True,
        "status_code": 200,
        "message": "Aadhaar verified successfully",
        "data": {
            "application_id": application_id,
            "resume_name": resume_name,
            "aadhaar_name": aadhaar_name,
            "aadhaar_verification_status": "passed",
            "name_match_score": name_match_score,
            "name_match_passed": True,
            "masked_aadhaar_number": masked_aadhaar_number,
            "aadhaar_photo_stored": bool(aadhaar_photo_path),
            "photo_match_status": photo_match.get("status"),
            "next_step": "face",
        },
    }


def _failure(
    *,
    message: str,
    status_code: int,
    application_id: str,
    application: dict,
    aadhaar_detection: dict | None = None,
    aadhaar_fields: dict | None = None,
    next_step: str,
) -> dict:
    resume = application.get("resume", {})

    aadhaar_name = _extract_aadhaar_name(aadhaar_fields)
    resume_name = _extract_resume_name(application)
    masked_aadhaar_number = _get_masked_aadhaar_number(aadhaar_fields)

    failure_result = {
        "verification_status": "failed",
        "aadhaar_detected": (aadhaar_detection or {}).get("is_aadhaar", False),
        "aadhaar_confidence": (aadhaar_detection or {}).get("confidence"),
        "extracted_name": aadhaar_name,
        "masked_aadhaar_number": masked_aadhaar_number,
        "dob": (aadhaar_fields or {}).get("dob", ""),
        "gender": (aadhaar_fields or {}).get("gender", ""),
        "aadhaar_photo_path": "",
        "name_match_score": None,
        "name_match_passed": False,
        "photo_match": {
            "status": "not_done",
            "score": None,
            "message": "Verification failed before photo matching.",
        },
        "updated_at": datetime.now(timezone.utc),
    }

    _safe_update_kyc(application_id, failure_result)

    debug_data = {
        "resume_name": resume_name or resume.get("candidate_name", ""),
        "aadhaar_name": aadhaar_name,
        "aadhaar_detected": (aadhaar_detection or {}).get("is_aadhaar", False),
        "aadhaar_confidence": (aadhaar_detection or {}).get("confidence"),
        "aadhaar_detection_message": (aadhaar_detection or {}).get("message", ""),
        "next_step": next_step,
    }

    if aadhaar_fields:
        debug_data["aadhaar_field_message"] = aadhaar_fields.get("message", "")
        debug_data["ocr_text_preview"] = aadhaar_fields.get("ocr_text_preview", "")

    return {
        "success": False,
        "status_code": status_code,
        "message": message,
        "data": debug_data,
    }
