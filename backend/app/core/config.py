from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


CORE_DIR = Path(__file__).resolve().parent
APP_ROOT = CORE_DIR.parent
BACKEND_ROOT = APP_ROOT.parent
PROJECT_ROOT = BACKEND_ROOT.parent
CONFIG_FILE = CORE_DIR / "config.json"

_CONFIG: dict[str, Any] | None = None


DEFAULT_CONFIG: dict[str, Any] = {
    "paths": {
        "project_root": str(PROJECT_ROOT),
        "backend_root": str(BACKEND_ROOT),
        "temp_dir": str(BACKEND_ROOT / "temp"),
        "cache_dir": str(BACKEND_ROOT / "cache"),
        "model_dir": str(BACKEND_ROOT / "models"),
        "report_temp_dir": str(BACKEND_ROOT / "temp" / "reports"),
        "resume_temp_dir": str(BACKEND_ROOT / "temp" / "resumes"),
        "resume_photo_temp_dir": str(BACKEND_ROOT / "temp" / "resume_photos"),
        "id_temp_dir": str(BACKEND_ROOT / "temp" / "ids"),
        "face_temp_dir": str(BACKEND_ROOT / "temp" / "faces"),
        "candidate_temp_dir": str(BACKEND_ROOT / "temp" / "candidates"),
        "live_frame_temp_dir": str(BACKEND_ROOT / "temp" / "live_frames"),
        "aadhaar_photo_temp_dir": str(BACKEND_ROOT / "temp" / "aadhaar_photos"),
        "whisper_model_dir": str(BACKEND_ROOT / "models" / "whisper"),
        "id_venv_python": str(PROJECT_ROOT / "id_venv" / "Scripts" / "python.exe"),
        "indian_id_inference": str(PROJECT_ROOT / "indian-id-validator" / "inference.py"),
        "env_file": str(PROJECT_ROOT / ".env"),
    },
    "models": {
        "qwen_model": "qwen2.5:7b",
        "ollama_base_url": "http://127.0.0.1:11434",
        "whisper_model": "medium",
        "face_model_path": "",
        "indian_id_model_path": "",
        "ocr_model_path": "",
    },
    "database": {
        "mongo_uri_env": "MONGO_URI",
        "mongo_db_name_env": "MONGO_DB_NAME",
        "default_mongo_uri": "mongodb://localhost:27017",
        "default_mongo_db_name": "novac_ai_interview",
    },
}


def get_config() -> dict[str, Any]:
    global _CONFIG

    if _CONFIG is None:
        config = deepcopy(DEFAULT_CONFIG)
        if CONFIG_FILE.exists():
            try:
                config = _deep_merge(config, json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
            except Exception as error:
                print(f"[Config] Could not read config.json, using defaults: {error}")

        config["paths"] = {key: str(_resolve_path(value)) for key, value in config.get("paths", {}).items()}
        _apply_env_overrides(config)
        _ensure_directories(config)
        _CONFIG = config

    return _CONFIG


def get_path(name: str) -> Path:
    value = get_config().get("paths", {}).get(name)
    if not value:
        raise KeyError(f"Path config not found: {name}")
    return Path(value)


def get_model_config(name: str, default: Any = "") -> Any:
    return get_config().get("models", {}).get(name, default)


def get_database_config() -> dict[str, str]:
    database = get_config().get("database", {})
    uri_env = database.get("mongo_uri_env", "MONGO_URI")
    db_env = database.get("mongo_db_name_env", "MONGO_DB_NAME")
    return {
        "mongo_uri": os.getenv(uri_env, database.get("default_mongo_uri", "mongodb://localhost:27017")),
        "db_name": os.getenv(db_env, database.get("default_mongo_db_name", "novac_ai_interview")),
    }


def _resolve_path(value: Any) -> Path:
    path = Path(str(value or ""))
    if path.is_absolute():
        return path
    return (CORE_DIR / path).resolve()


def _ensure_directories(config: dict[str, Any]) -> None:
    for key, value in config.get("paths", {}).items():
        if key.endswith("_dir") or key in {"temp_dir", "cache_dir", "model_dir"}:
            Path(value).mkdir(parents=True, exist_ok=True)


def _apply_env_overrides(config: dict[str, Any]) -> None:
    models = config.setdefault("models", {})
    models["qwen_model"] = os.getenv("QWEN_MODEL", models.get("qwen_model", "qwen2.5:7b"))
    models["ollama_base_url"] = os.getenv("QWEN_BASE_URL", models.get("ollama_base_url", "http://127.0.0.1:11434"))
    models["whisper_model"] = os.getenv("WHISPER_MODEL", models.get("whisper_model", "medium"))
    if os.getenv("WHISPER_MODEL_DIR"):
        config.setdefault("paths", {})["whisper_model_dir"] = str(_resolve_path(os.getenv("WHISPER_MODEL_DIR")))


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base
