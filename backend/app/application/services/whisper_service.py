from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from app.core.config import get_model_config, get_path

logger = logging.getLogger(__name__)

FALLBACK_MODELS = ("medium", "small", "base")

_WHISPER_MODEL = None
_WHISPER_MODEL_NAME = None


def transcribe_audio(audio_path: str | Path) -> dict:
    path = Path(audio_path)
    print(f"[Whisper] whisper started path={path}")

    if not path.exists():
        return {
            "success": False,
            "message": "Audio file was not saved correctly.",
            "transcript": "",
        }

    try:
        model = _get_whisper_model()
        started_at = time.perf_counter()
        segments, info = model.transcribe(str(path), beam_size=5)
        transcript = " ".join(segment.text.strip() for segment in segments if segment.text).strip()
        duration = time.perf_counter() - started_at
        print(
            f"[Whisper] selected_model={_WHISPER_MODEL_NAME} "
            f"transcription_duration={duration:.2f}s "
            f"transcript_length={len(transcript)} "
            f"language={getattr(info, 'language', '')}"
        )
        return {
            "success": True,
            "transcript": transcript,
            "language": getattr(info, "language", ""),
            "model": _WHISPER_MODEL_NAME,
        }
    except Exception as error:
        logger.exception("Whisper transcription failed")
        print(f"[Whisper] whisper error={error}")
        return {
            "success": False,
            "message": "Could not transcribe answer. Please record again.",
            "transcript": "",
            "model": _WHISPER_MODEL_NAME,
        }


def _get_whisper_model():
    global _WHISPER_MODEL, _WHISPER_MODEL_NAME

    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL

    try:
        from faster_whisper import WhisperModel
    except Exception as error:
        raise RuntimeError(
            "faster-whisper is not installed. Install requirements.txt before using voice transcription."
        ) from error

    configured_model = str(get_model_config("whisper_model", "medium"))
    preferred_model = os.getenv("WHISPER_MODEL", configured_model).strip() or configured_model
    model_dir = Path(os.getenv("WHISPER_MODEL_DIR", str(get_path("whisper_model_dir"))))
    model_dir.mkdir(parents=True, exist_ok=True)
    device = os.getenv("WHISPER_DEVICE", "cpu")
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    model_names = _get_model_fallback_order(preferred_model)

    for model_name in model_names:
        print(f"[Whisper] selected whisper model={model_name}")
        try:
            _WHISPER_MODEL = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
                download_root=str(model_dir),
            )
            _WHISPER_MODEL_NAME = model_name
            print(f"[Whisper] model load success model={model_name}")
            return _WHISPER_MODEL
        except Exception as error:
            logger.exception("Whisper model load failed for %s", model_name)
            print(f"[Whisper] model load failure model={model_name} error={error}")

    raise RuntimeError("Could not load Whisper transcription model.")


def _get_model_fallback_order(preferred_model: str) -> list[str]:
    ordered = [preferred_model]

    for model_name in FALLBACK_MODELS:
        if model_name not in ordered:
            ordered.append(model_name)

    return ordered
