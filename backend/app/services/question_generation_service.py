from __future__ import annotations

import json
from typing import Any

from app.services.db_service import get_job_by_id
from app.services.question_bank_service import load_question_bank
from app.services.qwen_service import (
    call_qwen_json,
    use_qwen_enabled,
)


QUESTION_COUNT = 5
DIFFICULTY_SPLIT = {
    "Easy": 2,
    "Medium": 2,
    "Hard": 1,
}


def generate_interview_questions(application: dict) -> dict:
    question_bank_questions = _load_application_question_bank(application)

    if question_bank_questions:
        return {
            "success": True,
            "source": "question_bank",
            "question_source": "question_bank",
            "candidate_name": _get_candidate_name(application),
            "question_bank_id": str(application.get("job_id") or ""),
            "question_bank_name": _get_job_title(application),
            "questions": question_bank_questions,
        }

    fallback_questions = _generate_rule_based_questions(application)

    if not use_qwen_enabled():
        return {
            "success": True,
            "source": "rule_based_fallback",
            "candidate_name": _get_candidate_name(application),
            "questions": fallback_questions,
            "qwen_error": "USE_QWEN is false",
        }

    parsed = call_qwen_json(
        _build_question_prompt(application),
        system_prompt=(
            "You are an interview intelligence engine for an ATS product. "
            "You generate resume-grounded interview questions and return JSON only."
        ),
        temperature=0.25,
        prompt_type="question_generation",
    )

    if parsed.get("success") is False:
        return {
            "success": False,
            "source": "qwen",
            "question_source": "qwen",
            "candidate_name": _get_candidate_name(application),
            "questions": [],
            "message": _clean_qwen_error(parsed.get("message")),
            "qwen_error": _clean_qwen_error(parsed.get("qwen_error") or parsed.get("message")),
        }

    questions, normalization_warning = _prepare_final_questions(
        parsed.get("questions"),
        fallback_questions,
    )

    return {
        "success": True,
        "source": "qwen",
        "question_source": "qwen",
        "candidate_name": parsed.get("candidate_name") or _get_candidate_name(application),
        "questions": questions,
        **({"qwen_warning": normalization_warning} if normalization_warning else {}),
    }


def _fallback_response(application: dict, questions: list[dict], qwen_error: str | None) -> dict:
    return {
        "success": True,
        "source": "rule_based_fallback",
        "question_source": "qwen",
        "candidate_name": _get_candidate_name(application),
        "questions": questions,
        "qwen_error": _clean_qwen_error(qwen_error or "Qwen unavailable"),
    }


def _build_question_prompt(application: dict) -> str:
    context = _build_resume_context(application)

    return f"""
Return ONLY valid JSON.
Do not include markdown.
Do not include explanation.
Do not wrap in ```json.

Return EXACTLY 5 questions.
The difficulty split must be exactly:
- 2 Easy
- 2 Medium
- 1 Hard

Required category mix:
1. Resume Overview - Easy
2. Project-Based Technical - Easy or Medium
3. Skill-Based Technical - Medium
4. System Design / Architecture / Debugging - Medium or Hard
5. Behavioral / HR / ATS Gap - Hard or Easy depending on content

Required JSON schema:
{{
  "candidate_name": "",
  "questions": [
    {{
      "id": "q1",
      "category": "",
      "difficulty": "Easy | Medium | Hard",
      "question": "",
      "expected_focus": ""
    }}
  ]
}}

Question quality rules:
- The questions must be varied across resume areas.
- Questions must be based on common ground between the HR job role skills and the candidate resume/projects.
- Prefer topics that appear in both the job requirements and the resume.
- Do not ask role-skill questions that are not supported by the resume unless it is the single ATS gap question.
- Do not repeat the same project more than twice.
- Do not ask multiple questions with the same expected answer.
- Do not invent fake projects.
- Do not ask about Java if the resume only says JavaScript.
- Do not ask about SQL as a present skill if SQL is missing.
- If ATS missing skills exist, ask at most one gap question.
- Mention actual projects/skills where possible.
- Prefer questions about FastAPI, React, OCR, PaddleOCR, OpenCV, AI/ML, MongoDB, document fraud detection, ATS matching, face verification, and deployable pipelines if present in resume.

Resume and ATS context:
{json.dumps(context, ensure_ascii=False, indent=2)}
""".strip()


def _build_resume_context(application: dict) -> dict:
    sections = _get_sections(application)
    ats_result = application.get("ats_result") or application.get("result") or {}
    job = get_job_by_id(application.get("job_id")) or {}
    resume_skills = _first_non_empty(
        application.get("skills"),
        _section_items(sections, "skills"),
        _safe_get(application, ["resume", "skills"]),
    )
    job_skills = job.get("required_skills") or []

    return {
        "candidate_name": _get_candidate_name(application),
        "job": {
            "id": job.get("id") or application.get("job_id"),
            "title": job.get("title", ""),
            "description": job.get("description", ""),
            "required_skills": job_skills,
            "education": job.get("education", ""),
            "experience": job.get("experience", 0),
            "keywords": job.get("keywords", []),
        },
        "skills": resume_skills,
        "common_skills": _common_strings(resume_skills, job_skills),
        "projects": _first_non_empty(
            application.get("projects"),
            _section_items(sections, "projects"),
            _safe_get(application, ["resume", "projects"]),
        ),
        "experience": _first_non_empty(
            application.get("experience"),
            _section_items(sections, "experience"),
            _safe_get(application, ["resume", "experience"]),
        ),
        "education": _first_non_empty(
            application.get("education"),
            _section_items(sections, "education"),
            _safe_get(application, ["resume", "education"]),
        ),
        "ats_result": ats_result,
        "matched_skills": _first_non_empty(
            application.get("matched_skills"),
            ats_result.get("matched_skills") if isinstance(ats_result, dict) else None,
        ),
        "missing_skills": _first_non_empty(
            application.get("missing_skills"),
            ats_result.get("missing_skills") if isinstance(ats_result, dict) else None,
        ),
        "resume_text": _get_resume_text(application)[:12000],
    }


def _load_application_question_bank(application: dict) -> list[dict]:
    job_id = application.get("job_id")

    if not job_id:
        return []

    bank_questions = load_question_bank(str(job_id))

    if not bank_questions:
        return []

    normalized_questions = [
        {
            "id": f"q{index}",
            "question_id": question.get("id") or f"q{index}",
            "category": question.get("category") or "Question Bank",
            "skill": question.get("category") or "",
            "difficulty": _normalize_difficulty(question.get("difficulty")),
            "question": question.get("question"),
            "expected_answer": question.get("expected_answer") or "",
            "expected_focus": "",
            "source": "question_bank",
        }
        for index, question in enumerate(bank_questions, start=1)
        if question.get("question")
    ]

    return _select_question_bank_questions(normalized_questions)


def _select_question_bank_questions(questions: list[dict]) -> list[dict]:
    if len(questions) <= QUESTION_COUNT:
        return _renumber_questions(questions)

    selected = []

    for difficulty, required_count in DIFFICULTY_SPLIT.items():
        for question in questions:
            if len([item for item in selected if item.get("difficulty") == difficulty]) >= required_count:
                break

            if question.get("difficulty") == difficulty and question not in selected:
                selected.append(question)

    for question in questions:
        if len(selected) >= QUESTION_COUNT:
            break

        if question not in selected:
            selected.append(question)

    return _renumber_questions(selected[:QUESTION_COUNT])


def _get_job_title(application: dict) -> str:
    job = get_job_by_id(application.get("job_id")) or {}
    return job.get("title") or str(application.get("job_role") or application.get("job_title") or "Question Bank")


def _clean_qwen_error(message: str | None) -> str:
    text = str(message or "Qwen did not return usable interview content.").strip()

    if "not available" in text.lower():
        return "Qwen did not return usable interview content after retry."

    return text


def _generate_rule_based_questions(application: dict) -> list[dict]:
    context = _build_resume_context(application)
    skills = _string_list(context.get("skills"))
    projects = _string_list(context.get("projects"))
    resume_text = str(context.get("resume_text") or "")
    primary_project = _pick_project(
        projects,
        resume_text,
        ["document fraud detection", "NOVAC document fraud detection", "fraud-detection platform"],
        "your most relevant AI/software project",
    )
    skill_project = _pick_project(
        projects,
        resume_text,
        ["vehicle damage detection", "EfficientNetB0", "MobileNetV2"],
        "your strongest model training project",
    )
    system_project = _pick_project(
        projects,
        resume_text,
        ["AI hiring platform", "ATS matching", "Aadhaar KYC", "face verification"],
        "your AI hiring platform",
    )
    primary_skill = _pick_first(skills, ["FastAPI", "PaddleOCR", "OpenCV", "AI/ML"])

    return [
        _question(
            "q1",
            "Resume Overview",
            "Easy",
            "Walk me through your resume and explain the two projects most relevant to an AI/software role.",
            "Communication, resume understanding, project prioritization",
        ),
        _question(
            "q2",
            "Project-Based Technical",
            "Easy",
            f"Could you elaborate on your experience with {primary_project}, including the tools and backend flow you used?",
            "Project clarity, implementation details, ownership",
        ),
        _question(
            "q3",
            "Skill-Based Technical",
            "Medium",
            _build_skill_question(skill_project, primary_skill),
            "Technical correctness, model or framework knowledge, practical depth",
        ),
        _question(
            "q4",
            "System Design / Debugging",
            "Medium",
            f"In {system_project}, how would you design the pipeline from resume upload to ATS screening, Aadhaar verification, face verification, and interview question generation?",
            "Pipeline design, ATS matching, verification boundaries",
        ),
        _question(
            "q5",
            "Behavioral/HR",
            "Hard",
            "Tell me about a difficult bug or model integration issue you faced and how you systematically debugged it.",
            "Debugging discipline, ownership, communication under uncertainty",
        ),
    ]


def _normalize_questions(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []

    questions = []

    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue

        question_text = str(item.get("question") or "").strip()

        if not question_text:
            continue

        questions.append(
            {
                "id": str(item.get("id") or f"q{index}"),
                "category": str(item.get("category") or "Interview").strip(),
                "difficulty": _normalize_difficulty(item.get("difficulty")),
                "question": question_text,
                "expected_focus": str(item.get("expected_focus") or "").strip(),
            }
        )

    return questions


def _prepare_final_questions(raw_questions: Any, fallback_questions: list[dict]) -> tuple[list[dict], str | None]:
    normalized = _dedupe_questions(_normalize_questions(raw_questions))
    selected = []
    category_counts = {}
    warning_parts = []

    for difficulty, required_count in DIFFICULTY_SPLIT.items():
        difficulty_questions = [
            question
            for question in normalized
            if question.get("difficulty") == difficulty
        ]

        for question in difficulty_questions:
            if len([item for item in selected if item.get("difficulty") == difficulty]) >= required_count:
                break

            category = question.get("category") or "Interview"

            if category_counts.get(category, 0) >= 2:
                continue

            selected.append(question)
            category_counts[category] = category_counts.get(category, 0) + 1

    for fallback_question in fallback_questions:
        if len(selected) >= QUESTION_COUNT and _has_required_split(selected):
            break

        difficulty = fallback_question.get("difficulty")

        if len([item for item in selected if item.get("difficulty") == difficulty]) >= DIFFICULTY_SPLIT.get(difficulty, 0):
            continue

        category = fallback_question.get("category") or "Interview"

        if category_counts.get(category, 0) >= 2:
            continue

        if _question_text_key(fallback_question) in {_question_text_key(item) for item in selected}:
            continue

        selected.append(fallback_question)
        category_counts[category] = category_counts.get(category, 0) + 1

    if len(normalized) != QUESTION_COUNT:
        warning_parts.append(f"Qwen returned {len(normalized)} usable questions; normalized to {QUESTION_COUNT}.")

    if not _has_required_split(selected):
        selected = fallback_questions[:]
        warning_parts.append("Qwen difficulty split was invalid; fallback questions were used.")

    return _renumber_questions(selected[:QUESTION_COUNT]), " ".join(warning_parts) or None


def _dedupe_questions(questions: list[dict]) -> list[dict]:
    seen = set()
    deduped = []

    for question in questions:
        key = _question_text_key(question)

        if key in seen:
            continue

        seen.add(key)
        deduped.append(question)

    return deduped


def _renumber_questions(questions: list[dict]) -> list[dict]:
    return [
        {
            **question,
            "id": f"q{index}",
        }
        for index, question in enumerate(questions, start=1)
    ]


def _has_required_split(questions: list[dict]) -> bool:
    if len(questions) != QUESTION_COUNT:
        return False

    return all(
        len([question for question in questions if question.get("difficulty") == difficulty]) == count
        for difficulty, count in DIFFICULTY_SPLIT.items()
    )


def _question_text_key(question: dict) -> str:
    return " ".join(str(question.get("question") or "").lower().split())


def _question(
    question_id: str,
    category: str,
    difficulty: str,
    question: str,
    expected_focus: str,
) -> dict:
    return {
        "id": question_id,
        "category": category,
        "difficulty": difficulty,
        "question": question,
        "expected_focus": expected_focus,
    }


def _normalize_difficulty(value: Any) -> str:
    difficulty = str(value or "Medium").strip().title()
    return difficulty if difficulty in {"Easy", "Medium", "Hard"} else "Medium"


def _get_candidate_name(application: dict) -> str:
    return (
        application.get("candidate_name")
        or _safe_get(application, ["resume", "candidate_name"])
        or application.get("resume_name")
        or application.get("file_name")
        or "Candidate"
    )


def _get_resume_text(application: dict) -> str:
    return (
        application.get("resume_text")
        or application.get("extracted_text")
        or _safe_get(application, ["resume", "text"])
        or _safe_get(application, ["resume", "extracted_text"])
        or _safe_get(application, ["resume", "raw_text"])
        or _safe_get(application, ["ats_ready_data", "raw_text"])
        or _safe_get(application, ["ats_ready_data", "normalized_text"])
        or _safe_get(application, ["resume", "ats_ready_data", "raw_text"])
        or _safe_get(application, ["resume", "ats_ready_data", "normalized_text"])
        or ""
    )


def _get_sections(application: dict) -> dict:
    return (
        _safe_get(application, ["ats_ready_data", "sections_detected"])
        or _safe_get(application, ["resume", "ats_ready_data", "sections_detected"])
        or {}
    )


def _section_items(sections: dict, section_name: str) -> list:
    section = sections.get(section_name, {}) if isinstance(sections, dict) else {}

    if isinstance(section, dict):
        return section.get("items", [])

    if isinstance(section, list):
        return section

    return []


def _safe_get(mapping: dict, keys: list[str]):
    current = mapping

    for key in keys:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def _first_non_empty(*values):
    for value in values:
        if value:
            return value

    return []


def _common_strings(left, right) -> list[str]:
    left_values = _string_list(left)
    right_values = _string_list(right)
    common = []

    for right_item in right_values:
        right_key = right_item.lower()

        if any(right_key in left_item.lower() or left_item.lower() in right_key for left_item in left_values):
            common.append(right_item)

    return common


def _string_list(value) -> list[str]:
    if not value:
        return []

    if not isinstance(value, list):
        value = [value]

    strings = []

    for item in value:
        if isinstance(item, dict):
            text = (
                item.get("name")
                or item.get("title")
                or item.get("skill")
                or item.get("raw_text")
                or item.get("description")
                or json.dumps(item, ensure_ascii=False)
            )
        else:
            text = item

        text = str(text or "").strip()

        if text:
            strings.append(text)

    return strings


def _pick_first(values: list[str], defaults: list[str]) -> str:
    for value in values:
        if value:
            return value

    return defaults[0]


def _pick_project(projects: list[str], resume_text: str, keywords: list[str], fallback: str) -> str:
    searchable_projects = projects or []

    for keyword in keywords:
        for project in searchable_projects:
            if keyword.lower() in project.lower():
                return project

        if keyword.lower() in resume_text.lower():
            return keyword

    return searchable_projects[0] if searchable_projects else fallback


def _build_skill_question(skill_project: str, primary_skill: str) -> str:
    if "efficientnet" in skill_project.lower() or "vehicle damage" in skill_project.lower():
        return "Can you walk us through the process of training your EfficientNetB0 model for vehicle damage detection using transfer learning?"

    return f"How have you applied {primary_skill} in {skill_project}, and what technical trade-offs did you make?"
