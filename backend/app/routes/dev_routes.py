from fastapi import APIRouter
from pathlib import Path
import shutil

from app.services.db_service import clear_old_application_records
from app.services.json_storage_service import clear_interview_results, clear_interview_sessions
from app.services.mongo_interview_service import clear_interview_candidates


router = APIRouter()


@router.post("/clear-old-records")
def clear_old_records(clear_applications: bool = False, clear_files: bool = False):
    application_result = clear_old_application_records(clear_applications=clear_applications)
    cleared_sessions = clear_interview_sessions()
    cleared_results = clear_interview_results()
    mongo_error = None

    try:
        cleared_mongo_candidates = clear_interview_candidates()
    except Exception as error:
        cleared_mongo_candidates = 0
        mongo_error = str(error)

    cleared_files = _clear_uploaded_interview_files() if clear_files else 0
    cleared_applications = (
        application_result.get("applications_cleared", 0)
        or application_result.get("applications_updated", 0)
        or 0
    )

    return {
        "success": True,
        "message": "Old records cleared. Uploaded files were only deleted when clear_files=true.",
        "clear_applications": clear_applications,
        "clear_files": clear_files,
        "cleared": {
            "interview_sessions": cleared_sessions,
            "interview_results": cleared_results,
            "mongo_interview_candidates": cleared_mongo_candidates,
            "uploaded_interview_files": cleared_files,
            "applications": cleared_applications,
        },
        "mongo_error": mongo_error,
        **application_result,
    }


def _clear_uploaded_interview_files() -> int:
    project_root = Path(__file__).resolve().parents[3]
    targets = [
        project_root / "backend" / "uploads" / "audio_answers",
        project_root / "backend" / "uploads" / "transcripts",
        project_root / "backend" / "uploads" / "whisper_tests",
        project_root / "backend" / "app" / "storage" / "interview_audio",
        project_root / "backend" / "app" / "storage" / "live_frames",
        project_root / "backend" / "app" / "storage" / "text",
    ]
    removed = 0

    for target in targets:
        if not target.exists() or not target.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue

        for child in target.iterdir():
            if child.is_dir():
                removed += sum(1 for path in child.rglob("*") if path.is_file())
                shutil.rmtree(child)
            else:
                child.unlink(missing_ok=True)
                removed += 1

        target.mkdir(parents=True, exist_ok=True)

    (project_root / "backend" / "uploads" / "whisper_tests" / "transcripts").mkdir(
        parents=True,
        exist_ok=True,
    )

    return removed
