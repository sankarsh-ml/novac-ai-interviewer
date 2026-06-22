from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import requests


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_QWEN_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_QWEN_MODEL = "qwen2.5:7b"
QWEN_TIMEOUT_SECONDS = 90


def call_qwen(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float = 0.3,
) -> dict:
    base_url = _get_config("QWEN_BASE_URL", DEFAULT_QWEN_BASE_URL).rstrip("/")
    model = _get_config("QWEN_MODEL", DEFAULT_QWEN_MODEL)
    final_prompt = _build_final_prompt(prompt, system_prompt)

    payload = {
        "model": model,
        "prompt": final_prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }

    try:
        response = requests.post(
            f"{base_url}/api/generate",
            json=payload,
            timeout=QWEN_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()

        return {
            "success": True,
            "response": data.get("response", ""),
            "model": model,
        }
    except Exception as error:
        message = f"Qwen unavailable: {error}"
        logger.exception(message)
        return {
            "success": False,
            "message": message,
        }


def is_qwen_available() -> dict:
    base_url = _get_config("QWEN_BASE_URL", DEFAULT_QWEN_BASE_URL).rstrip("/")
    model = _get_config("QWEN_MODEL", DEFAULT_QWEN_MODEL)
    result = call_qwen(
        "Return exactly this JSON: {\"ok\": true}",
        system_prompt="You are a health check endpoint. Return only JSON.",
        temperature=0,
    )

    if result.get("success"):
        return {
            "success": True,
            "qwen_available": True,
            "model": model,
            "base_url": base_url,
        }

    return {
        "success": False,
        "qwen_available": False,
        "message": result.get("message", "Qwen unavailable"),
        "model": model,
        "base_url": base_url,
    }


def extract_json_from_qwen_response(text: str) -> dict:
    if not text or not str(text).strip():
        return {
            "success": False,
            "message": "Qwen returned an empty response",
        }

    cleaned_text = _strip_markdown_fence(str(text).strip())
    decoder = json.JSONDecoder()

    for index, character in enumerate(cleaned_text):
        if character not in "[{":
            continue

        try:
            parsed, _ = decoder.raw_decode(cleaned_text[index:])
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, dict):
            return parsed

        return {
            "success": False,
            "message": "Qwen returned JSON, but not a JSON object",
        }

    return {
        "success": False,
        "message": "Qwen response did not contain valid JSON",
    }


def use_qwen_enabled() -> bool:
    return _get_config("USE_QWEN", "true").strip().lower() in {"1", "true", "yes", "on"}


def get_qwen_config() -> dict:
    return {
        "base_url": _get_config("QWEN_BASE_URL", DEFAULT_QWEN_BASE_URL).rstrip("/"),
        "model": _get_config("QWEN_MODEL", DEFAULT_QWEN_MODEL),
        "use_qwen": use_qwen_enabled(),
    }


def _build_final_prompt(prompt: str, system_prompt: str | None) -> str:
    if not system_prompt:
        return prompt

    return f"System instructions:\n{system_prompt}\n\nUser request:\n{prompt}"


def _strip_markdown_fence(text: str) -> str:
    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        return "\n".join(lines).strip()

    return text


def _get_config(name: str, default: str) -> str:
    env_value = os.getenv(name)

    if env_value not in (None, ""):
        return env_value

    dotenv_value = _read_dotenv_value(name)

    if dotenv_value not in (None, ""):
        return dotenv_value

    return default


def _read_dotenv_value(name: str) -> str | None:
    dotenv_path = PROJECT_ROOT / ".env"

    if not dotenv_path.exists():
        return None

    try:
        for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)

            if key.strip() == name:
                return value.strip().strip('"').strip("'")
    except Exception as error:
        logger.warning("Could not read .env for Qwen config: %s", error)

    return None
