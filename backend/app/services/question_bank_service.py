import csv
import json
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1]
QUESTION_BANK_DIR = APP_DIR / "storage" / "question_banks"

QUESTION_BANK_DIR.mkdir(
    parents=True,
    exist_ok=True
)


def save_question_bank(job_id, questions):
    normalized_questions = normalize_question_bank_questions(questions)

    file_path = (
        QUESTION_BANK_DIR /
        f"{job_id}.json"
    )

    with open(
        file_path,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            {
                "job_id": job_id,
                "questions": normalized_questions
            },
            f,
            indent=4
        )


def load_question_bank(job_id):

    file_path = (
        QUESTION_BANK_DIR /
        f"{job_id}.json"
    )

    if not file_path.exists():
        return []

    with open(
        file_path,
        "r",
        encoding="utf-8"
    ) as f:
        data = json.load(f)

    return normalize_question_bank_questions(
        data.get(
            "questions",
            []
        )
    )


def normalize_question_bank_questions(questions: Any) -> list[dict]:
    if not isinstance(questions, list):
        return []

    normalized = []

    for index, item in enumerate(questions, start=1):
        if not isinstance(item, dict):
            continue

        question_text = str(item.get("question") or item.get("Question") or "").strip()

        if not question_text:
            continue

        expected_answer = str(
            item.get("expected_answer")
            or item.get("expectedAnswer")
            or item.get("answer")
            or item.get("ANS")
            or ""
        ).strip()

        normalized.append(
            {
                "id": str(item.get("id") or item.get("question_id") or f"q{index}"),
                "question": question_text,
                "expected_answer": expected_answer,
                "difficulty": _normalize_difficulty(item.get("difficulty")),
                "category": str(
                    item.get("category")
                    or item.get("skill")
                    or item.get("topic")
                    or item.get("skill_category")
                    or "Question Bank"
                ).strip(),
            }
        )

    return normalized


def parse_question_bank_text(content: str) -> list[dict]:
    stripped = content.strip()

    if not stripped:
        return []

    if "," in stripped.splitlines()[0] or "\t" in stripped.splitlines()[0]:
        parsed = _parse_delimited_question_bank(stripped)

        if parsed:
            return parsed

    return _parse_plain_text_question_bank(stripped)


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
                    "question": lowered.get("question") or lowered.get("questions"),
                    "expected_answer": lowered.get("expected_answer")
                    or lowered.get("expected answer")
                    or lowered.get("answer"),
                    "difficulty": lowered.get("difficulty"),
                    "category": lowered.get("category")
                    or lowered.get("skill")
                    or lowered.get("topic"),
                }
            )
    except Exception:
        return []

    return normalize_question_bank_questions(rows)


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
                }
            )
            index += 2
            continue

        if current.endswith("?"):
            questions.append(
                {
                    "question": _strip_question_prefix(current),
                    "expected_answer": "",
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
    difficulty = str(value or "Medium").strip().title()
    return difficulty if difficulty in {"Easy", "Medium", "Hard"} else "Medium"
