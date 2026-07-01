from __future__ import annotations


def is_available_for_quick_select(application: dict) -> bool:
    decision = str(application.get("hr_decision") or "").lower()
    interview_status = str(application.get("interview_status") or application.get("interviewStatus") or "").lower()
    return decision != "rejected" and decision != "selected" and interview_status not in {"completed", "in_progress"}
