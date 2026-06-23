from __future__ import annotations

import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path


TRANSCRIPT_DIR = Path("uploads/transcripts")
TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)


def _log_step(message: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[Whisper Step {timestamp}] {message}", flush=True)


@lru_cache(maxsize=1)
def _get_model():
    """
    Load faster-whisper once per backend process.
    It will not reload for every answer unless the backend restarts/reloads.
    """
    from faster_whisper import WhisperModel

    started_at = time.perf_counter()
    _log_step("1/4 Import successful. Starting model load...")

    model = WhisperModel(
        "base",
        device="cpu",
        compute_type="int8",
        download_root="models/whisper",
    )

    elapsed = time.perf_counter() - started_at
    _log_step(f"2/4 Model loaded and cached in {elapsed:.2f}s")

    return model


def preload_model() -> bool:
    """
    Call this before interview starts so first answer is faster.
    """
    _log_step("Preload requested")
    _get_model()
    _log_step("Preload complete. Whisper is ready.")
    return True


def transcribe_audio(audio_path: str) -> str:
    """
    Reuse cached faster-whisper model for transcription.
    """
    total_started_at = time.perf_counter()
    audio_file = Path(audio_path)

    _log_step(f"Transcription requested for: {audio_file}")

    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    size_bytes = audio_file.stat().st_size
    _log_step(f"Audio file exists. Size: {size_bytes} bytes")

    if size_bytes == 0:
        raise ValueError("Audio file is empty. Frontend did not record audio correctly.")

    _log_step("Getting cached Whisper model...")
    model = _get_model()

    _log_step("3/4 Starting transcription...")
    transcribe_started_at = time.perf_counter()

    segments, info = model.transcribe(
        str(audio_file),
        beam_size=1,
        vad_filter=True,
    )

    _log_step(
        "Transcription generator created. "
        f"Detected language: {getattr(info, 'language', 'unknown')}, "
        f"duration: {getattr(info, 'duration', 'unknown')}"
    )

    transcript_parts = []
    segment_count = 0

    for segment in segments:
        segment_count += 1
        text = segment.text.strip()

        _log_step(
            f"Segment {segment_count}: "
            f"{segment.start:.2f}s → {segment.end:.2f}s | {text}"
        )

        if text:
            transcript_parts.append(text)

    transcript = " ".join(transcript_parts).strip()

    transcribe_elapsed = time.perf_counter() - transcribe_started_at
    total_elapsed = time.perf_counter() - total_started_at

    _log_step(f"4/4 Transcription finished. Segments: {segment_count}")
    _log_step(f"Transcript length: {len(transcript)} characters")
    _log_step(f"Transcription time: {transcribe_elapsed:.2f}s")
    _log_step(f"Total Whisper service time: {total_elapsed:.2f}s")

    if not transcript:
        _log_step("WARNING: Transcript is empty. Audio may be silent or unreadable.")

    return transcript


def transcribe_and_save(audio_path: str, session_id: str, question_id: str) -> dict:
    """
    Transcribe audio and save transcript as .txt.
    """
    _log_step("Starting transcribe_and_save")
    transcript = transcribe_audio(audio_path)

    safe_session_id = _safe_file_part(session_id)
    safe_question_id = _safe_file_part(question_id)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    transcript_file = TRANSCRIPT_DIR / f"{safe_session_id}_{safe_question_id}_{timestamp}.txt"

    _log_step(f"Saving transcript to: {transcript_file}")

    with open(transcript_file, "w", encoding="utf-8") as file:
        file.write(transcript or "")

    _log_step("Transcript saved successfully")

    return {
        "transcript": transcript or "",
        "transcript_file_path": str(transcript_file),
    }


def _safe_file_part(value: str) -> str:
    safe = "".join(
        character if character.isalnum() or character in ("-", "_") else "_"
        for character in str(value)
    )
    return safe[:80] or "audio"