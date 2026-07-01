from __future__ import annotations

import json
import logging
import os
from typing import Any

import requests

from app.core.config import get_model_config, get_path

logger = logging.getLogger(__name__)

QWEN_TIMEOUT_SECONDS = 90


def call_qwen(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float = 0,
    prompt_type: str = "general",
    json_mode: bool = True,
    top_p: float = 0.8,
    num_predict: int = 600,
) -> dict:
    base_url = _get_config("QWEN_BASE_URL", str(get_model_config("ollama_base_url", "http://127.0.0.1:11434"))).rstrip("/")
    model = _get_config("QWEN_MODEL", str(get_model_config("qwen_model", "qwen2.5:7b")))
    final_prompt = _build_final_prompt(prompt, system_prompt)

    payload = {
        "model": model,
        "prompt": final_prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": top_p,
            "num_predict": num_predict,
        },
    }

    if json_mode:
        payload["format"] = "json"

    print(
        f"[Qwen] prompt_type={prompt_type} endpoint={base_url}/api/generate "
        f"model={model} json_mode={json_mode}"
    )

    try:
        response = _post_generate(base_url, payload)
        used_json_mode = json_mode

        if response.status_code >= 400 and json_mode:
            print(
                f"[Qwen] prompt_type={prompt_type} json_mode_failed_status={response.status_code} "
                "retry_without_format=true"
            )
            payload_without_format = dict(payload)
            payload_without_format.pop("format", None)
            response = _post_generate(base_url, payload_without_format)
            used_json_mode = False

        response.raise_for_status()
        data = response.json()
        response_text = str(data.get("response") or "").strip()
        print(
            f"[Qwen] prompt_type={prompt_type} response_length={len(response_text)} "
            f"json_mode_used={used_json_mode}"
        )

        unusable_message = _get_unusable_response_message(response_text)

        if unusable_message:
            print(f"[Qwen] prompt_type={prompt_type} unusable_response={unusable_message}")
            return {
                "success": False,
                "message": unusable_message,
                "response": response_text,
                "model": model,
                "base_url": base_url,
                "json_mode_used": used_json_mode,
            }

        return {
            "success": True,
            "response": response_text,
            "model": model,
            "base_url": base_url,
            "json_mode_used": used_json_mode,
        }
    except requests.Timeout as error:
        message = f"Qwen timed out after {QWEN_TIMEOUT_SECONDS}s: {error}"
        logger.exception(message)
        print(f"[Qwen] prompt_type={prompt_type} timeout={error}")
        return {
            "success": False,
            "message": message,
            "model": model,
            "base_url": base_url,
            "json_mode_used": json_mode,
        }
    except requests.RequestException as error:
        message = f"Qwen unavailable or model not running: {error}"
        logger.exception(message)
        print(f"[Qwen] prompt_type={prompt_type} request_error={error}")
        return {
            "success": False,
            "message": message,
            "model": model,
            "base_url": base_url,
            "json_mode_used": json_mode,
        }
    except Exception as error:
        message = f"Qwen unavailable: {error}"
        logger.exception(message)
        print(f"[Qwen] prompt_type={prompt_type} error={error}")
        return {
            "success": False,
            "message": message,
            "model": model,
            "base_url": base_url,
            "json_mode_used": json_mode,
        }


def call_qwen_json(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float = 0.3,
    prompt_type: str = "general",
) -> dict:
    first_result = call_qwen(
        prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        prompt_type=prompt_type,
    )
    parsed = _parse_qwen_json_result(first_result, prompt_type)

    if parsed.get("success") is not False:
        return parsed

    retry_prompt = (
        "Your previous response was unusable. Return ONLY one valid JSON object. "
        "No markdown, no prose, no placeholders, no 'not available'.\n\n"
        f"{prompt}"
    )
    print(f"[Qwen] prompt_type={prompt_type} retrying_with_strict_prompt=true")
    retry_result = call_qwen(
        retry_prompt,
        system_prompt=system_prompt,
        temperature=0,
        prompt_type=prompt_type,
    )
    return _parse_qwen_json_result(retry_result, prompt_type)


def is_qwen_available() -> dict:
    base_url = _get_config("QWEN_BASE_URL", str(get_model_config("ollama_base_url", "http://127.0.0.1:11434"))).rstrip("/")
    model = _get_config("QWEN_MODEL", str(get_model_config("qwen_model", "qwen2.5:7b")))

    try:
        response = requests.get(f"{base_url}/api/tags", timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as error:
        logger.exception("Could not reach Ollama for Qwen health check")
        print(f"[Qwen] health_check endpoint={base_url}/api/tags request_error={error}")
        return {
            "success": False,
            "qwen_available": False,
            "message": "Qwen model is not available. Please start Ollama and load qwen2.5:7b.",
            "model": model,
            "base_url": base_url,
        }
    except Exception as error:
        logger.exception("Invalid Ollama health check response")
        print(f"[Qwen] health_check endpoint={base_url}/api/tags error={error}")
        return {
            "success": False,
            "qwen_available": False,
            "message": "Qwen model is not available. Please start Ollama and load qwen2.5:7b.",
            "model": model,
            "base_url": base_url,
        }

    models = _extract_ollama_model_names(data)
    model_available = model in models
    print(
        f"[Qwen] health_check endpoint={base_url}/api/tags model={model} "
        f"model_available={model_available}"
    )

    if model_available:
        return {
            "success": True,
            "qwen_available": True,
            "model": model,
            "base_url": base_url,
        }

    return {
        "success": False,
        "qwen_available": False,
        "message": "Qwen model is not available. Please start Ollama and load qwen2.5:7b.",
        "model": model,
        "base_url": base_url,
    }


def extract_json_from_qwen_response(text: str) -> dict:
    unusable_message = _get_unusable_response_message(str(text or ""))

    if unusable_message:
        return {
            "success": False,
            "message": unusable_message,
        }

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


def _parse_qwen_json_result(result: dict, prompt_type: str) -> dict:
    if not result.get("success"):
        return {
            "success": False,
            "message": result.get("message", "Qwen unavailable"),
            "qwen_error": result.get("message", "Qwen unavailable"),
            "model": result.get("model"),
            "base_url": result.get("base_url"),
            "json_mode_used": result.get("json_mode_used"),
        }

    parsed = extract_json_from_qwen_response(result.get("response", ""))

    if parsed.get("success") is False:
        print(f"[Qwen] prompt_type={prompt_type} parse_failure={parsed.get('message')}")
        return {
            "success": False,
            "message": parsed.get("message", "Could not parse Qwen response"),
            "qwen_error": parsed.get("message", "Could not parse Qwen response"),
            "model": result.get("model"),
            "base_url": result.get("base_url"),
            "json_mode_used": result.get("json_mode_used"),
        }

    return {
        **parsed,
        "model": result.get("model"),
        "base_url": result.get("base_url"),
        "json_mode_used": result.get("json_mode_used"),
    }


def _post_generate(base_url: str, payload: dict) -> requests.Response:
    return requests.post(
        f"{base_url}/api/generate",
        json=payload,
        timeout=QWEN_TIMEOUT_SECONDS,
    )


def _extract_ollama_model_names(data: Any) -> set[str]:
    models = data.get("models") if isinstance(data, dict) else []
    names: set[str] = set()

    if not isinstance(models, list):
        return names

    for item in models:
        if not isinstance(item, dict):
            continue

        for key in ("name", "model"):
            value = str(item.get(key) or "").strip()

            if value:
                names.add(value)

    return names


def _get_unusable_response_message(text: str) -> str:
    stripped = str(text or "").strip()

    if not stripped:
        return "Qwen returned an empty response"

    lowered = stripped.lower()
    unusable_phrases = (
        "not available",
        "model not found",
        "model is not running",
        "no response",
        "cannot answer",
    )

    if lowered in unusable_phrases or any(phrase == lowered for phrase in unusable_phrases):
        return f"Qwen returned unusable output: {stripped[:120]}"

    if len(stripped) <= 32 and any(phrase in lowered for phrase in unusable_phrases):
        return f"Qwen returned unusable output: {stripped[:120]}"

    return ""


def use_qwen_enabled() -> bool:
    return _get_config("USE_QWEN", "true").strip().lower() in {"1", "true", "yes", "on"}


def get_qwen_config() -> dict:
    return {
        "base_url": _get_config("QWEN_BASE_URL", str(get_model_config("ollama_base_url", "http://127.0.0.1:11434"))).rstrip("/"),
        "model": _get_config("QWEN_MODEL", str(get_model_config("qwen_model", "qwen2.5:7b"))),
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
    dotenv_path = get_path("env_file")

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
