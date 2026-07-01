from __future__ import annotations

import json
import re
from typing import Any

from app.application.services.question_generation_service import _build_resume_context
from app.application.services.qwen_service import call_qwen, get_qwen_config, is_qwen_available


REQUIRED_GRADING_KEYS = (
    "finalScore",
    "relevance",
    "technical",
    "depth",
    "clarity",
    "feedback",
    "missingPoints",
)

SCORE_KEYS = ("finalScore", "relevance", "technical", "depth", "clarity")


def evaluate_answer_with_qwen(
    application: dict,
    question: dict,
    answer_text: str,
    question_index: int | None = None,
    question_source: str | None = None,
) -> dict:
    """
    Qwen-only answer grading.

    This function never uses a deterministic fallback score. If Qwen cannot return a
    valid grading object, the caller receives gradingStatus=grading_failed and should
    allow retry.
    """
    config = get_qwen_config()
    candidate_id = application.get("application_id") or application.get("_id") or ""
    question_id = str(question.get("id") or question.get("question_id") or "")
    transcript = str(answer_text or "").strip()
    source = question_source or _get_question_source(application)

    print(
        "[Qwen grading] "
        f"candidateId={candidate_id} "
        f"questionIndex={question_index if question_index is not None else ''} "
        f"questionId={question_id} "
        f"questionSource={source} "
        f"transcriptLength={len(transcript)} "
        f"endpoint={config.get('base_url')}/api/generate "
        f"model={config.get('model')}"
    )

    health = is_qwen_available()
    if not health.get("success"):
        return _grading_error(
            health.get("message")
            or "Qwen model is not available. Please start Ollama and load qwen2.5:7b.",
            reason="Qwen unavailable",
            model=config.get("model"),
            base_url=config.get("base_url"),
        )

    prompt = _build_evaluation_prompt(application, question, transcript)
    result = _call_qwen_grader(prompt)

    if not result.get("success"):
        return _grading_error(
            "Qwen grading failed. Please retry answer evaluation.",
            reason=result.get("message") or "Qwen request failed",
            model=result.get("model") or config.get("model"),
            base_url=result.get("base_url") or config.get("base_url"),
            json_mode_used=result.get("json_mode_used"),
        )

    parsed = _parse_and_validate_grading(result.get("response", ""))
    _log_parse_result("initial", parsed, result)

    if not parsed.get("success"):
        parsed = _repair_qwen_output(result.get("response", ""), config)

    # Qwen sometimes copies the 0-valued schema while still writing positive feedback.
    # That is invalid grading for a non-empty, relevant answer, so force a Qwen regrade.
    if (
        parsed.get("success")
        and _looks_like_copied_zero_schema(parsed.get("grading", {}), transcript)
    ):
        print(
            "[Qwen grading] all_zero_with_positive_feedback=true "
            "retrying_full_regrade=true"
        )
        regrade_result = _call_qwen_grader(
            _build_zero_score_regrade_prompt(application, question, transcript, parsed["grading"]),
            prompt_type="answer_grading_regrade",
        )
        if regrade_result.get("success"):
            regrade_parsed = _parse_and_validate_grading(regrade_result.get("response", ""))
            _log_parse_result("regrade", regrade_parsed, regrade_result)
            if regrade_parsed.get("success"):
                parsed = regrade_parsed

    if not parsed.get("success"):
        print(
            "[Qwen grading] "
            f"candidateId={candidate_id} questionId={question_id} "
            "finalValidGrading=false"
        )
        return _grading_error(
            "Qwen grading failed. Please retry answer evaluation.",
            reason=parsed.get("message") or "Invalid JSON from Qwen",
            model=result.get("model") or config.get("model"),
            base_url=result.get("base_url") or config.get("base_url"),
            json_mode_used=result.get("json_mode_used"),
        )

    grading = parsed["grading"]
    print(
        "[Qwen grading] parsedGradingBeforeSave="
        f"{json.dumps(grading, ensure_ascii=False)}"
    )
    print(
        "[Qwen grading] "
        f"candidateId={candidate_id} questionId={question_id} finalValidGrading=true"
    )

    return {
        "success": True,
        "status": "success",
        "gradingStatus": "graded",

        # Top-level fields for current frontend compatibility.
        "finalScore": grading["finalScore"],
        "score": grading["finalScore"],
        "relevance": grading["relevance"],
        "technical": grading["technical"],
        "depth": grading["depth"],
        "clarity": grading["clarity"],
        "feedback": grading["feedback"],
        "missingPoints": grading["missingPoints"],
        "missing_points": grading["missingPoints"],

        # Nested object for future compatibility.
        "grading": {
            "finalScore": grading["finalScore"],
            "score": grading["finalScore"],
            "relevance": grading["relevance"],
            "technical": grading["technical"],
            "depth": grading["depth"],
            "clarity": grading["clarity"],
            "feedback": grading["feedback"],
            "missingPoints": grading["missingPoints"],
            "gradingStatus": "graded",
            "gradingModel": result.get("model") or config.get("model"),
        },

        "gradingModel": result.get("model") or config.get("model"),
        "model": result.get("model") or config.get("model"),
        "base_url": result.get("base_url") or config.get("base_url"),
        "json_mode_used": result.get("json_mode_used"),
    }


def _call_qwen_grader(prompt: str, prompt_type: str = "answer_grading") -> dict:
    return call_qwen(
        prompt,
        system_prompt=(
            "You are a strict but fair technical interviewer. "
            "You MUST return exactly one valid JSON object and nothing else."
        ),
        temperature=0,
        prompt_type=prompt_type,
        json_mode=True,
        top_p=0.7,
        num_predict=700,
    )


def _build_evaluation_prompt(application: dict, question: dict, answer_text: str) -> str:
    context = _build_resume_context(application)
    job_role = (
        application.get("job_role")
        or application.get("job_title")
        or application.get("role")
        or ""
    )
    required_skills = (
        application.get("required_skills")
        or application.get("skills")
        or application.get("matched_skills")
        or []
    )
    expected_answer = str(
        question.get("expected_answer")
        or question.get("expectedAnswer")
        or question.get("expected_focus")
        or ""
    ).strip()

    # Keep the schema, but explicitly tell Qwen not to copy the zero values.
    return f"""
You are grading a spoken interview answer.

CRITICAL OUTPUT RULES:
Return ONLY one valid JSON object.
Do not include markdown.
Do not include ```json.
Do not include text before or after the JSON.
Do not include comments.
Do not include trailing commas.
Do not use null values.
Do not write "not available".

Required JSON keys:
{{
  "finalScore": 0,
  "relevance": 0,
  "technical": 0,
  "depth": 0,
  "clarity": 0,
  "feedback": "string",
  "missingPoints": ["string"]
}}

SCORING RULES:
- Replace the 0 values above with actual marks.
- Scores must be numbers from 0 to 10.
- Do NOT copy the schema values.
- Use 0 only when the candidate answer is empty, completely irrelevant, or completely wrong.
- If the candidate answer is partially correct, every relevant rubric score must be above 0.
- Expected answer is a guide, not an exact wording requirement.
- Give credit for semantically correct answers even if wording differs.
- Grade based on semantic correctness, relevance, technical accuracy, depth, and clarity.
- For question bank questions, use the expected answer strongly but do not require exact wording.
- If there is no expected answer, compare the answer against your own ideal answer internally.

Job role/title:
{job_role}

Required skills:
{json.dumps(required_skills, ensure_ascii=False)}

Resume context:
{json.dumps(context, ensure_ascii=False, indent=2)[:12000]}

Question object:
{json.dumps(question, ensure_ascii=False, indent=2)}

Expected answer:
{expected_answer}

Candidate transcript/answer:
{answer_text}

Now return JSON only.
""".strip()


def _build_repair_prompt(invalid_response: str) -> str:
    return f"""
Convert the following invalid grading output into valid JSON only.
Do not grade again.
Do not explain.
Do not include markdown.

Required schema:
{{
  "finalScore": 0,
  "relevance": 0,
  "technical": 0,
  "depth": 0,
  "clarity": 0,
  "feedback": "string",
  "missingPoints": ["string"]
}}

Invalid response:
{invalid_response}
""".strip()


def _build_zero_score_regrade_prompt(
    application: dict,
    question: dict,
    answer_text: str,
    previous_grading: dict,
) -> str:
    expected_answer = str(
        question.get("expected_answer")
        or question.get("expectedAnswer")
        or question.get("expected_focus")
        or ""
    ).strip()
    job_role = application.get("job_role") or application.get("job_title") or application.get("role") or ""
    required_skills = application.get("required_skills") or application.get("skills") or []

    return f"""
Your previous grading returned all numeric scores as 0 but the feedback appeared to say the answer had correct content.

Re-grade from scratch using Qwen only.

Return ONLY valid JSON:
{{
  "finalScore": 0,
  "relevance": 0,
  "technical": 0,
  "depth": 0,
  "clarity": 0,
  "feedback": "string",
  "missingPoints": ["string"]
}}

Rules:
- Do not copy the zero schema.
- Use 0 only if the answer is empty, fully irrelevant, or fully wrong.
- If the answer is semantically close to the expected answer, assign non-zero marks.
- Scores must be numbers from 0 to 10.

Job role:
{job_role}

Required skills:
{json.dumps(required_skills, ensure_ascii=False)}

Question:
{json.dumps(question, ensure_ascii=False, indent=2)}

Expected answer:
{expected_answer}

Candidate answer:
{answer_text}

Previous invalid grading:
{json.dumps(previous_grading, ensure_ascii=False)}

Return JSON only.
""".strip()


def _repair_qwen_output(invalid_response: str, config: dict) -> dict:
    repair_result = call_qwen(
        _build_repair_prompt(invalid_response),
        system_prompt="Convert invalid grading output into valid JSON only. Do not grade again.",
        temperature=0,
        prompt_type="answer_grading_repair",
        json_mode=True,
        top_p=0.7,
        num_predict=500,
    )

    if repair_result.get("success"):
        parsed = _parse_and_validate_grading(repair_result.get("response", ""))
        _log_parse_result("repair", parsed, repair_result)
        return parsed

    print(
        "[Qwen grading] "
        f"repairRetrySuccess=false reason={repair_result.get('message')}"
    )
    return {
        "success": False,
        "message": repair_result.get("message") or "Invalid JSON from Qwen",
        "model": repair_result.get("model") or config.get("model"),
        "base_url": repair_result.get("base_url") or config.get("base_url"),
    }


def _parse_and_validate_grading(text: str) -> dict:
    direct = _direct_json_parse(text)
    direct_success = isinstance(direct, dict)
    print(f"[Qwen grading] directParseSuccess={direct_success}")

    parsed = direct
    extracted_success = False

    if not isinstance(parsed, dict):
        parsed = _extract_json_object(text)
        extracted_success = isinstance(parsed, dict)

    print(f"[Qwen grading] extractedJsonParseSuccess={extracted_success}")

    if not isinstance(parsed, dict):
        return {"success": False, "message": "Invalid JSON from Qwen"}

    normalized = _normalize_grading_aliases(parsed)
    validation_error = _validate_grading(normalized)

    if validation_error:
        print(f"[Qwen grading] validation_error={validation_error} parsed={json.dumps(parsed, ensure_ascii=False)[:800]}")
        return {"success": False, "message": validation_error}

    grading = {
        "finalScore": normalize_score(normalized["finalScore"]),
        "relevance": normalize_score(normalized["relevance"]),
        "technical": normalize_score(normalized["technical"]),
        "depth": normalize_score(normalized["depth"]),
        "clarity": normalize_score(normalized["clarity"]),
        "feedback": str(normalized["feedback"]).strip(),
        "missingPoints": _normalize_string_list(normalized["missingPoints"]),
    }

    return {"success": True, "grading": grading}


def _direct_json_parse(text: str) -> Any:
    try:
        return json.loads(str(text or "").strip())
    except Exception:
        return None


def _extract_json_object(text: str) -> Any:
    cleaned = _strip_markdown_fences(str(text or "").strip())

    # First try robust raw_decode from each possible opening brace.
    decoder = json.JSONDecoder()
    for index, character in enumerate(cleaned):
        if character != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(cleaned[index:])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    # Fallback: first { through last }.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return None

    try:
        return json.loads(cleaned[start : end + 1])
    except Exception:
        return None


def _strip_markdown_fences(text: str) -> str:
    text = str(text or "").strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _normalize_grading_aliases(value: dict) -> dict:
    """
    Normalize both flat and nested Qwen outputs.

    Qwen often returns one of:
    - {"scores": {"relevance": 8, ...}, "feedback": "..."}
    - {"grading": {"final_score": "8/10", ...}}
    - {"evaluation": {...}}
    This function accepts those while still requiring all final canonical fields.
    """
    root = _unwrap_likely_grading_container(value)

    aliases = {
        "finalScore": (
            "finalScore", "final_score", "score", "overallScore", "overall_score",
            "totalScore", "total_score", "overall", "total", "marks", "grade",
        ),
        "relevance": ("relevance", "relevanceScore", "relevance_score", "relevancy"),
        "technical": (
            "technical", "technicalScore", "technical_score", "technicalAccuracy",
            "technical_accuracy", "accuracy", "correctness", "technicalCorrectness",
        ),
        "depth": ("depth", "depthScore", "depth_score", "detail", "detailScore"),
        "clarity": ("clarity", "clarityScore", "clarity_score", "communication"),
        "feedback": ("feedback", "comments", "analysis", "explanation", "summary", "reason"),
        "missingPoints": (
            "missingPoints", "missing_points", "missing", "improvements",
            "areasToImprove", "areas_to_improve", "gaps", "weaknesses",
        ),
    }

    normalized = dict(root)

    for canonical, possible_keys in aliases.items():
        if canonical in normalized and normalized[canonical] not in (None, ""):
            continue

        found = _find_first_deep(value, possible_keys)
        if found is not None:
            normalized[canonical] = found

    # If finalScore is missing, compute it from rubric scores only if Qwen supplied
    # rubric scores. This is not a fallback grader; it only aggregates Qwen's marks.
    if "finalScore" not in normalized or normalized.get("finalScore") in (None, ""):
        rubric_values = [
            normalized.get("relevance"),
            normalized.get("technical"),
            normalized.get("depth"),
            normalized.get("clarity"),
        ]
        if all(item not in (None, "") for item in rubric_values):
            normalized["finalScore"] = round(
                (
                    normalize_score(normalized["relevance"]) * 0.30
                    + normalize_score(normalized["technical"]) * 0.35
                    + normalize_score(normalized["depth"]) * 0.20
                    + normalize_score(normalized["clarity"]) * 0.15
                ),
                1,
            )

    return normalized


def _unwrap_likely_grading_container(value: dict) -> dict:
    if not isinstance(value, dict):
        return {}

    for key in (
        "grading",
        "evaluation",
        "result",
        "scores",
        "rubric",
        "assessment",
        "grade",
    ):
        nested = value.get(key)
        if isinstance(nested, dict):
            merged = dict(value)
            merged.update(nested)
            return merged

    return dict(value)


def _find_first_deep(value: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        # Exact, case-sensitive first.
        for key in keys:
            if key in value and value[key] not in (None, ""):
                return value[key]

        # Case/underscore insensitive.
        wanted = {_key_signature(key) for key in keys}
        for key, item in value.items():
            if _key_signature(key) in wanted and item not in (None, ""):
                return item

        for item in value.values():
            found = _find_first_deep(item, keys)
            if found is not None:
                return found

    elif isinstance(value, list):
        for item in value:
            found = _find_first_deep(item, keys)
            if found is not None:
                return found

    return None


def _key_signature(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key or "").lower())


def _validate_grading(value: dict) -> str:
    for key in REQUIRED_GRADING_KEYS:
        if key not in value:
            return f"Missing required key: {key}"
        if value[key] is None:
            return f"Invalid null value for key: {key}"

    for key in SCORE_KEYS:
        numeric = normalize_score(value.get(key))
        if numeric < 0 or numeric > 10:
            return f"Score out of range for key: {key}"
        value[key] = numeric

    feedback = str(value.get("feedback") or "").strip()
    if not feedback:
        return "Feedback is required"
    if "not available" in feedback.lower():
        return "Feedback contains disallowed placeholder"
    value["feedback"] = feedback

    value["missingPoints"] = _normalize_string_list(value.get("missingPoints"))

    for item in value["missingPoints"]:
        if item is None or "not available" in str(item).lower():
            return "missingPoints contains invalid item"

    return ""


def _normalize_string_list(value) -> list[str]:
    if value is None or value == "":
        return []

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item or "").strip()]

    # Split common single-string formats.
    text = str(value).strip()
    if not text:
        return []
    if "\n" in text or ";" in text:
        parts = re.split(r"[\n;]+", text)
        return [part.strip(" -•\t") for part in parts if part.strip(" -•\t")]
    return [text]


def normalize_score(value) -> float | int:
    if value is None or isinstance(value, bool):
        return 0

    if isinstance(value, (int, float)):
        return _clean_score_number(float(value))

    if isinstance(value, dict):
        # Qwen may return {"score": 8, "reason": "..."}.
        nested = _find_first_deep(value, ("score", "value", "marks", "rating"))
        if nested is not None and nested is not value:
            return normalize_score(nested)
        return 0

    text = str(value or "").strip()
    if not text:
        return 0

    # Handle "8/10", "Score: 8/10", "8.5", etc.
    fraction = re.search(r"(-?\d+(?:\.\d+)?)\s*/\s*10", text)
    if fraction:
        return _clean_score_number(float(fraction.group(1)))

    percent = re.search(r"(-?\d+(?:\.\d+)?)\s*%", text)
    if percent:
        return _clean_score_number(float(percent.group(1)) / 10)

    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return 0

    try:
        return _clean_score_number(float(match.group(0)))
    except ValueError:
        return 0


def _clean_score_number(score: float) -> float | int:
    score = float(max(0, min(10, score)))
    if score.is_integer():
        return int(score)
    return round(score, 1)


def _looks_like_copied_zero_schema(grading: dict, transcript: str) -> bool:
    if len(str(transcript or "").split()) < 4:
        return False

    all_scores_zero = all(normalize_score(grading.get(key)) == 0 for key in SCORE_KEYS)
    if not all_scores_zero:
        return False

    feedback = str(grading.get("feedback") or "").lower()
    positive_markers = (
        "correct",
        "mostly correct",
        "partially correct",
        "good",
        "identified",
        "mentioned",
        "relevant",
        "accurate",
        "appropriate",
    )
    no_answer_markers = (
        "no answer",
        "empty",
        "irrelevant",
        "completely wrong",
        "not related",
    )

    return any(marker in feedback for marker in positive_markers) and not any(
        marker in feedback for marker in no_answer_markers
    )


def _grading_error(
    message: str,
    reason: str,
    model: str | None = None,
    base_url: str | None = None,
    json_mode_used: bool | None = None,
) -> dict:
    return {
        "success": False,
        "status": "error",
        "message": message,
        "reason": reason,
        "gradingStatus": "grading_failed",
        "gradingModel": model or get_qwen_config().get("model"),
        "model": model or get_qwen_config().get("model"),
        "base_url": base_url or get_qwen_config().get("base_url"),
        "json_mode_used": json_mode_used,
    }


def _log_parse_result(label: str, parsed: dict, result: dict) -> None:
    print(
        "[Qwen grading] "
        f"{label} responseLength={len(str(result.get('response') or ''))} "
        f"jsonModeUsed={result.get('json_mode_used')} "
        f"repairRetrySuccess={parsed.get('success') if label == 'repair' else ''} "
        f"valid={parsed.get('success')}"
    )


def _get_question_source(application: dict) -> str:
    payload = application.get("interview_questions")
    if isinstance(payload, dict):
        return str(payload.get("question_source") or payload.get("source") or "")
    return str(application.get("question_source") or application.get("questionSource") or "")
