import csv
import json
import uuid
from datetime import datetime
from typing import Any

from app.repositories import question_bank_repository


def save_question_bank(job_id, questions):
    normalized_questions = normalize_question_bank_questions(questions, job_id=str(job_id or ""))
    question_bank_repository.replace_for_job(str(job_id or ""), normalized_questions)
    print(f"[Storage] Saved question bank to MongoDB jobId={job_id} count={len(normalized_questions)}")


def load_question_bank(job_id):
    questions = question_bank_repository.list_for_job(str(job_id or ""))
    return normalize_question_bank_questions([question for question in questions if question], job_id=str(job_id or ""))


def normalize_question_bank_questions(questions: Any, job_id: str = "") -> list[dict]:
    if not isinstance(questions, list):
        return []

    normalized = []
    now = datetime.now().isoformat()

    for index, item in enumerate(questions, start=1):
        if not isinstance(item, dict):
            continue

        question_text = str(item.get("question") or item.get("Question") or item.get("text") or "").strip()

        if not question_text:
            continue

        expected_answer = str(
            item.get("expected_answer")
            or item.get("expectedAnswer")
            or item.get("ideal_answer")
            or item.get("answer")
            or item.get("ANS")
            or "N/A"
        ).strip() or "N/A"
        area = str(
            item.get("area_of_interest")
            or item.get("areaOfInterest")
            or item.get("category")
            or item.get("skill")
            or item.get("topic")
            or item.get("skill_category")
            or "General"
        ).strip() or "General"
        question_id = str(
            item.get("_id")
            or item.get("id")
            or item.get("question_id")
            or f"{job_id or 'question'}-{index}-{uuid.uuid4().hex[:8]}"
        )
        created_at = str(item.get("created_at") or item.get("createdAt") or now)

        normalized.append(
            {
                "_id": question_id,
                "id": question_id,
                "question_id": question_id,
                "question": question_text,
                "expected_answer": expected_answer,
                "expectedAnswer": expected_answer,
                "difficulty": _normalize_difficulty(item.get("difficulty")),
                "area_of_interest": area,
                "areaOfInterest": area,
                "category": area,
                "topic": area,
                "tags": _normalize_tags(item.get("tags")),
                "job_role": str(item.get("job_role") or item.get("jobRole") or "").strip(),
                "score_weight": _normalize_score_weight(item.get("score_weight") or item.get("scoreWeight")),
                "source": str(item.get("source") or "manual").strip() or "manual",
                "created_at": created_at,
                "updated_at": str(item.get("updated_at") or item.get("updatedAt") or now),
            }
        )

    return normalized


def filter_question_bank_questions(
    questions: list[dict],
    difficulty: str = "all",
    area_of_interest: str = "all",
    search: str = "",
    tags: list[str] | None = None,
    job_role: str = "all",
) -> list[dict]:
    normalized = normalize_question_bank_questions(questions)
    difficulty_filter = _normalize_filter_value(difficulty)
    area_filter = _normalize_filter_value(area_of_interest)
    role_filter = _normalize_filter_value(job_role)
    tag_filters = [_normalize_filter_value(tag) for tag in tags or [] if _normalize_filter_value(tag)]
    search_text = str(search or "").strip().lower()
    filtered = []

    for item in normalized:
        if difficulty_filter not in {"", "all"} and item.get("difficulty") != difficulty_filter:
            continue

        if area_filter not in {"", "all"} and _normalize_filter_value(item.get("area_of_interest")) != area_filter:
            continue

        if role_filter not in {"", "all"} and _normalize_filter_value(item.get("job_role")) != role_filter:
            continue

        item_tags = [_normalize_filter_value(tag) for tag in item.get("tags", [])]

        if tag_filters and not all(tag in item_tags for tag in tag_filters):
            continue

        if search_text:
            haystack = " ".join(
                [
                    item.get("question", ""),
                    item.get("expected_answer", ""),
                    item.get("area_of_interest", ""),
                    item.get("job_role", ""),
                    " ".join(item.get("tags", [])),
                ]
            ).lower()

            if search_text not in haystack:
                continue

        filtered.append(item)

    return filtered


def get_question_bank_filters(job_id: str) -> dict:
    questions = load_question_bank(job_id)

    return {
        "difficulties": ["easy", "medium", "hard"],
        "areas_of_interest": sorted({item.get("area_of_interest") or "General" for item in questions}),
        "job_roles": sorted({item.get("job_role") for item in questions if item.get("job_role")}),
        "tags": sorted({tag for item in questions for tag in item.get("tags", [])}),
    }


def parse_question_bank_text(content: str) -> list[dict]:
    stripped = content.strip()

    if not stripped:
        return []

    if stripped[0] in "[{":
        parsed = _parse_json_question_bank(stripped)

        if parsed:
            return parsed

    parsed = _parse_labelled_text_question_bank(stripped)

    if parsed:
        return parsed

    if "," in stripped.splitlines()[0] or "\t" in stripped.splitlines()[0]:
        parsed = _parse_delimited_question_bank(stripped)

        if parsed:
            return parsed

    return _parse_plain_text_question_bank(stripped)


def _parse_json_question_bank(content: str) -> list[dict]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []

    if isinstance(data, dict):
        data = data.get("questions", [])

    return normalize_question_bank_questions(data)


def _parse_delimited_question_bank(content: str) -> list[dict]:
    sample = content[:2048]

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t")
    except csv.Error:
        dialect = csv.excel

    rows = []

    try:
        reader = csv.DictReader(content.splitlines(), dialect=dialect)

        for row in reader:
            if not row:
                continue

            lowered = {str(key or "").strip().lower(): value for key, value in row.items()}
            rows.append(
                {
                    "question": lowered.get("question")
                    or lowered.get("questions")
                    or lowered.get("question_text")
                    or lowered.get("question text"),
                    "expected_answer": lowered.get("expected_answer")
                    or lowered.get("expected answer")
                    or lowered.get("ideal_answer")
                    or lowered.get("ideal answer")
                    or lowered.get("answer"),
                    "difficulty": lowered.get("difficulty") or lowered.get("level"),
                    "area_of_interest": lowered.get("area_of_interest")
                    or lowered.get("area of interest")
                    or lowered.get("topic")
                    or lowered.get("domain")
                    or lowered.get("area")
                    or lowered.get("expertise")
                    or lowered.get("area_of_expertise")
                    or lowered.get("area of expertise")
                    or lowered.get("category")
                    or lowered.get("skill"),
                    "tags": lowered.get("tags"),
                    "job_role": lowered.get("job_role") or lowered.get("job role") or lowered.get("role"),
                    "score_weight": lowered.get("score_weight") or lowered.get("score weight"),
                    "source": "uploaded_file",
                }
            )
    except Exception:
        return []

    return normalize_question_bank_questions(rows)


def _parse_labelled_text_question_bank(content: str) -> list[dict]:
    blocks = []
    current = []

    for line in content.splitlines():
        if line.strip() == "---":
            if current:
                blocks.append("\n".join(current))
                current = []
            continue

        current.append(line)

    if current:
        blocks.append("\n".join(current))

    parsed = []

    for block in blocks:
        item = _parse_labelled_question_block(block)

        if item.get("question"):
            parsed.append(item)

    return normalize_question_bank_questions(parsed)


def _parse_labelled_question_block(block: str) -> dict:
    item = {"source": "upload"}
    current_key = ""

    for raw_line in block.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if ":" in line:
            label, value = line.split(":", 1)
            field = _label_to_question_field(label)

            if field:
                item[field] = value.strip()
                current_key = field
                continue

        if current_key:
            item[current_key] = f"{item.get(current_key, '')} {line}".strip()

    return item


def _label_to_question_field(label: str) -> str:
    normalized = str(label or "").strip().lower().replace("_", " ")
    normalized = " ".join(normalized.split())
    aliases = {
        "question": "question",
        "q": "question",
        "expected answer": "expected_answer",
        "answer": "expected_answer",
        "ideal answer": "expected_answer",
        "difficulty": "difficulty",
        "level": "difficulty",
        "area of interest": "area_of_interest",
        "area": "area_of_interest",
        "topic": "area_of_interest",
        "domain": "area_of_interest",
        "area of expertise": "area_of_interest",
        "tags": "tags",
        "job role": "job_role",
        "role": "job_role",
    }

    return aliases.get(normalized, "")


def _parse_plain_text_question_bank(content: str) -> list[dict]:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    questions = []
    index = 0

    while index < len(lines):
        current = lines[index]
        next_line = lines[index + 1] if index + 1 < len(lines) else ""

        if next_line.upper().startswith(("A:", "ANS:", "ANS:=", "ANSWER:", "EXPECTED_ANSWER:")):
            question = _strip_question_prefix(current)
            answer = (
                next_line.replace("ANS:=", "")
                .replace("ANS:", "")
                .replace("A:", "")
                .replace("ANSWER:", "")
                .replace("EXPECTED_ANSWER:", "")
                .strip()
            )
            questions.append(
                {
                    "question": question,
                    "expected_answer": answer,
                    "source": "uploaded_file",
                }
            )
            index += 2
            continue

        if current.endswith("?"):
            questions.append(
                {
                    "question": _strip_question_prefix(current),
                    "expected_answer": "N/A",
                    "source": "uploaded_file",
                }
            )

        index += 1

    return normalize_question_bank_questions(questions)


def _strip_question_prefix(value: str) -> str:
    text = str(value or "").strip()

    if text.upper().startswith("Q:"):
        return text[2:].strip()

    for separator in (")", ".", "-"):
        parts = text.split(separator, 1)

        if len(parts) == 2 and parts[0].strip().isdigit():
            return parts[1].strip()

    return text


def _normalize_difficulty(value: Any) -> str:
    difficulty = str(value or "medium").strip().lower()
    return difficulty if difficulty in {"easy", "medium", "hard"} else "medium"


def _normalize_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_tags = value
    else:
        raw_tags = str(value or "").replace(";", ",").split(",")

    return [str(tag).strip() for tag in raw_tags if str(tag).strip()]


def _normalize_score_weight(value: Any) -> float:
    try:
        score_weight = float(value)
    except (TypeError, ValueError):
        return 1

    return score_weight if score_weight > 0 else 1


def _normalize_filter_value(value: Any) -> str:
    return str(value or "").strip().lower()
