from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import get_path
from app.infrastructure.database.mongo_service import get_database, make_json_safe


def save_file_to_mongo(
    content: bytes,
    filename: str,
    content_type: str = "application/octet-stream",
    metadata: dict | None = None,
) -> str:
    try:
        from gridfs import GridFS
    except Exception as error:
        from app.infrastructure.database.mongo_service import DatabaseUnavailableError

        raise DatabaseUnavailableError("Database unavailable. Please start MongoDB and try again.") from error

    db = get_database()
    file_id = GridFS(db).put(
        content,
        filename=filename,
        contentType=content_type,
        metadata=make_json_safe(metadata or {}),
    )
    print(f"[Storage] Saved file to GridFS fileId={file_id}")
    return str(file_id)


def save_path_to_mongo(path: str | Path, content_type: str = "application/octet-stream", metadata: dict | None = None) -> str:
    file_path = Path(path)
    return save_file_to_mongo(
        file_path.read_bytes(),
        filename=file_path.name,
        content_type=content_type,
        metadata=metadata,
    )


def read_file_from_mongo(file_id: str) -> dict | None:
    if not file_id:
        return None

    try:
        from bson import ObjectId
        from gridfs import GridFS
        from gridfs.errors import NoFile
    except Exception as error:
        from app.infrastructure.database.mongo_service import DatabaseUnavailableError

        raise DatabaseUnavailableError("Database unavailable. Please start MongoDB and try again.") from error

    try:
        grid_out = GridFS(get_database()).get(ObjectId(str(file_id)))
    except (NoFile, Exception):
        return None

    return {
        "content": grid_out.read(),
        "filename": grid_out.filename,
        "content_type": getattr(grid_out, "content_type", None)
        or getattr(grid_out, "contentType", None)
        or "application/octet-stream",
        "metadata": getattr(grid_out, "metadata", {}) or {},
    }


def delete_file_from_mongo(file_id: Any) -> bool:
    if not file_id:
        return False

    try:
        from bson import ObjectId
        from gridfs import GridFS
    except Exception:
        return False

    try:
        GridFS(get_database()).delete(ObjectId(str(file_id)))
        return True
    except Exception:
        return False


def materialize_file_from_mongo(file_id: str, suffix: str = "") -> Path | None:
    stored = read_file_from_mongo(file_id)

    if not stored:
        return None

    suffix = suffix or Path(stored.get("filename") or "").suffix
    temp_dir = get_path("temp_dir")
    temp_dir.mkdir(parents=True, exist_ok=True)
    import tempfile

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_dir)
    temp_file.write(stored["content"])
    temp_file.close()
    return Path(temp_file.name)
