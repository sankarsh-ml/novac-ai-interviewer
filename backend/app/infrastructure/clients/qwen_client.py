from __future__ import annotations

from app.application.services.qwen_service import call_qwen_json, is_qwen_available


def health() -> dict:
    return is_qwen_available()


def request_json(prompt: str, **kwargs) -> dict:
    return call_qwen_json(prompt, **kwargs)
