from __future__ import annotations

import json

from app.services.question_generation_service import _build_resume_context
from app.services.qwen_service import call_qwen, extract_json_from_qwen_response, use_qwen_enabled


def evaluate_answer_with_qwen(application: dict, question: dict, answer_text: str) -> dict:
    if not answer_text or not answer_text.strip():
        return {
            "success": False,
            "score": 0,
            "message": "Answer text is required",
        }

    if not use_qwen_enabled():
        return {
            "success": False,
            "score": 0,
            "message": "Qwen unavailable, answer evaluation skipped",
            "qwen_error": "USE_QWEN is false",
        }

    qwen_result = call_qwen(
        _build_evaluation_prompt(application, question, answer_text),
        system_prompt=(
            "You are a strict but fair technical interviewer. "
            "Evaluate only the provided answer against the resume and question. Return JSON only."
        ),
        temperature=0.2,
    )

    if not qwen_result.get("success"):
        return {
            "success": False,
            "score": 0,
            "message": "Qwen unavailable, answer evaluation skipped",
            "qwen_error": qwen_result.get("message", "Qwen unavailable"),
        }

    parsed = extract_json_from_qwen_response(qwen_result.get("response", ""))

    if parsed.get("success") is False:
        return {
            "success": False,
            "score": 0,
            "message": "Qwen unavailable, answer evaluation skipped",
            "qwen_error": parsed.get("message", "Could not parse Qwen response"),
        }

    relevance_score = _normalize_score(parsed.get("relevance_score"))
    final_score = _normalize_score(parsed.get("score"))

    mismatch_cap = _topic_mismatch_cap(question, answer_text)

    if mismatch_cap is not None:
        final_score = min(final_score, mismatch_cap)

    if relevance_score <= 1:
        final_score = min(final_score, 2)
    elif relevance_score <= 3:
        final_score = min(final_score, 4)

    return {
        "success": bool(parsed.get("success", True)),
        "score": final_score,
        "relevance_score": relevance_score,
        "technical_score": _normalize_score(parsed.get("technical_score")),
        "depth_score": _normalize_score(parsed.get("depth_score")),
        "clarity_score": _normalize_score(parsed.get("clarity_score")),
        "strengths": _normalize_string_list(parsed.get("strengths")),
        "weaknesses": _normalize_string_list(parsed.get("weaknesses")),
        "feedback": str(parsed.get("feedback") or "").strip(),
        "follow_up_question": str(parsed.get("follow_up_question") or "").strip(),
    }


def _build_evaluation_prompt(application: dict, question: dict, answer_text: str) -> str:
    context = _build_resume_context(application)

    return f"""
Return ONLY valid JSON.
Do not include markdown.
Do not include explanation.
Do not wrap in ```json.

You are a strict technical interviewer.
First check if the answer directly addresses the asked question.
If the answer is off-topic or mostly about a different project/skill, score it low.
A polished answer about the wrong topic should not receive a high score.
If relevance is poor, cap the score at 4/10.
If relevance is zero, cap the score at 2/10.
Do not reward resume knowledge unless it answers the current question.

Evaluate the candidate answer using these weighted criteria:
- Relevance to the exact question: 40%
- Technical correctness: 25%
- Depth and specificity: 20%
- Clarity and structure: 10%
- Resume consistency: 5%

Important examples:
- If the question asks about EfficientNetB0 training but the answer talks about a NOVAC OCR/FastAPI fraud detection pipeline, score around 2/10 or 3/10.
- If the question asks about face verification embeddings but the answer talks about ATS skill matching, score around 2/10 or 3/10.
- If the question asks about FastAPI backend routes but the answer talks about React UI styling only, score at most 4/10.
- If the question asks about NOVAC document fraud detection and the answer covers PaddleOCR, FastAPI, field validation, ELA/MVSS/TruFor, PDF handling, score high.

Score must be from 0 to 10.

Required JSON schema:
{{
  "success": true,
  "score": 0,
  "relevance_score": 0,
  "technical_score": 0,
  "depth_score": 0,
  "clarity_score": 0,
  "strengths": [],
  "weaknesses": [],
  "feedback": "",
  "follow_up_question": ""
}}

Resume context:
{json.dumps(context, ensure_ascii=False, indent=2)}

Question:
{json.dumps(question, ensure_ascii=False, indent=2)}

Candidate answer:
{answer_text.strip()}
""".strip()


def _normalize_score(score, default=0):
    """
    Safely normalize score values returned by Qwen/evaluator.
    Handles int, float, string numbers, and bad values.
    Returns a score between 0 and 10.
    """

    if score is None:
        return default

    try:
        if isinstance(score, str):
            score = score.strip()

            # Handle formats like "8/10"
            if "/" in score:
                score = score.split("/")[0].strip()

            # Handle formats like "80%"
            score = score.replace("%", "").strip()

        score_value = float(score)

    except (ValueError, TypeError):
        return default

    # Clamp score between 0 and 10
    score_value = max(0, min(10, score_value))


    return round(score_value, 2)


def _normalize_string_list(value) -> list[str]:
    if not value:
        return []

    if not isinstance(value, list):
        value = [value]

    return [str(item).strip() for item in value if str(item or "").strip()]


def _topic_mismatch_cap(question: dict, answer_text: str) -> int | None:
    question_text = " ".join(
        str(question.get(key) or "")
        for key in ("question", "category", "expected_focus")
    ).lower()
    answer = str(answer_text or "").lower()

    mismatch_rules = [
        {
            "question_terms": ["efficientnet", "vehicle damage", "transfer learning"],
            "answer_terms": ["efficientnet", "vehicle", "damage", "transfer", "fine-tun", "dataset", "augmentation", "imagenet"],
            "off_topic_terms": ["document fraud", "paddleocr", "ocr", "fastapi"],
            "cap": 3,
        },
        {
            "question_terms": ["face verification", "embedding", "arcface", "insightface"],
            "answer_terms": ["face", "embedding", "arcface", "insightface", "cosine", "threshold"],
            "off_topic_terms": ["ats", "skill matching", "resume screening"],
            "cap": 3,
        },
        {
            "question_terms": ["fastapi", "backend route", "api route"],
            "answer_terms": ["fastapi", "backend", "route", "endpoint", "pydantic", "request", "response"],
            "off_topic_terms": ["react", "css", "ui styling", "frontend styling"],
            "cap": 4,
        },
    ]

    for rule in mismatch_rules:
        if not any(term in question_text for term in rule["question_terms"]):
            continue

        has_relevant_term = any(term in answer for term in rule["answer_terms"])
        has_off_topic_term = any(term in answer for term in rule["off_topic_terms"])

        if has_off_topic_term and not has_relevant_term:
            return rule["cap"]

    return None
