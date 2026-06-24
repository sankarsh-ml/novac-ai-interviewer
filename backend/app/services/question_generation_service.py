from __future__ import annotations

import json
from typing import Any

from app.services.application_store_service import get_job_by_id
from app.services.qwen_service import (
    call_qwen,
    extract_json_from_qwen_response,
    use_qwen_enabled,
)


QUESTION_COUNT = 5
DIFFICULTY_SPLIT = {
    "Easy": 2,
    "Medium": 2,
    "Hard": 1,
}


def generate_interview_questions(application: dict) -> dict:
    fallback_questions = _generate_rule_based_questions(application)

    if not use_qwen_enabled():
        return {
            "success": True,
            "source": "rule_based_fallback",
            "candidate_name": _get_candidate_name(application),
            "questions": fallback_questions,
            "qwen_error": "USE_QWEN is false",
        }

    qwen_result = call_qwen(
        _build_question_prompt(application),
        system_prompt=(
            "You are an interview intelligence engine for an ATS product. "
            "You generate resume-grounded interview questions and return JSON only."
        ),
        temperature=0.25,
    )

    if not qwen_result.get("success"):
        return _fallback_response(application, fallback_questions, qwen_result.get("message"))

    parsed = extract_json_from_qwen_response(qwen_result.get("response", ""))

    if parsed.get("success") is False:
        return _fallback_response(application, fallback_questions, parsed.get("message"))

    questions, normalization_warning = _prepare_final_questions(
        parsed.get("questions"),
        fallback_questions,
    )

    return {
        "success": True,
        "source": "qwen",
        "candidate_name": parsed.get("candidate_name") or _get_candidate_name(application),
        "questions": questions,
        **({"qwen_warning": normalization_warning} if normalization_warning else {}),
    }


def _fallback_response(application: dict, questions: list[dict], qwen_error: str | None) -> dict:
    return {
        "success": True,
        "source": "rule_based_fallback",
        "candidate_name": _get_candidate_name(application),
        "questions": questions,
        "qwen_error": qwen_error or "Qwen unavailable",
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
1. Project + Job Skill - Easy
2. Project + Job Skill - Easy or Medium
3. Skill-Based Technical - Medium
4. System Design / Architecture / Debugging - Medium or Hard
5. Required Skill Gap / Learning - Hard or Medium if a required skill is missing

Required JSON schema:
{{
  "candidate_name": "",
  "questions": [
    {{
      "id": "q1",
      "category": "",
      "difficulty": "Easy | Medium | Hard",
      "question": "",
      "expected_focus": "",
      "job_skill": "",
      "resume_evidence": ""
    }}
  ]
}}

Question quality rules:
- Questions must be based on common ground between the HR job role and the candidate resume.
- At least 2 questions must directly reference candidate projects.
- At least 2 questions must directly reference required job skills.
- At least 1 question should test how the candidate would learn/integrate one missing required skill if any are missing.
- Do not repeat the same project more than twice.
- Do not ask multiple questions with the same expected answer.
- Do not invent fake projects.
- Do not ask about Java if the resume only says JavaScript.
- Do not ask about SQL as a present skill if SQL is missing.
- If ATS missing skills exist, ask at most one gap question.
- Mention actual projects/skills where possible.
- Use job_title, required_skills, resume_skills, resume_projects, common_skills, missing_skills, and candidate project/internship highlights.
- Prefer production software engineering, maintainability, deployment, security, APIs, and data handling when the job role requires them.

Job, resume, common-ground, and ATS context:
{json.dumps(context, ensure_ascii=False, indent=2)}
""".strip()


def _build_resume_context(application: dict) -> dict:
    sections = _get_sections(application)
    ats_result = application.get("ats_result") or application.get("result") or {}
    job = get_job_by_id(application.get("job_id")) or {}
    resume_text = _get_resume_text(application)
    resume_skills = _first_non_empty(
        application.get("skills"),
        _section_items(sections, "skills"),
        _safe_get(application, ["resume", "skills"]),
    )
    resume_projects = _first_non_empty(
        application.get("projects"),
        _section_items(sections, "projects"),
        _safe_get(application, ["resume", "projects"]),
    )
    resume_experience = _first_non_empty(
        application.get("experience"),
        _section_items(sections, "experience"),
        _safe_get(application, ["resume", "experience"]),
    )
    required_skills = _string_list(job.get("required_skills") or job.get("skills") or [])
    resume_skill_strings = _string_list(resume_skills)
    project_strings = _string_list(resume_projects)
    common_skills = _common_skills(required_skills, resume_skill_strings, project_strings, resume_text)
    missing_skills = [
        skill
        for skill in required_skills
        if skill.lower() not in {common.lower() for common in common_skills}
    ]

    return {
        "candidate_name": _get_candidate_name(application),
        "job_title": job.get("title") or job.get("job_title") or "",
        "required_skills": required_skills,
        "education_requirement": job.get("education") or job.get("education_requirement") or "",
        "job_description": job.get("description") or job.get("job_description") or "",
        "skills": resume_skills,
        "resume_skills": resume_skill_strings,
        "projects": resume_projects,
        "resume_projects": project_strings,
        "experience": resume_experience,
        "education": _first_non_empty(
            application.get("education"),
            _section_items(sections, "education"),
            _safe_get(application, ["resume", "education"]),
        ),
        "common_skills": common_skills,
        "missing_skills": missing_skills,
        "candidate_highlights": _candidate_highlights(resume_text),
        "ats_result": ats_result,
        "matched_skills": _first_non_empty(
            application.get("matched_skills"),
            ats_result.get("matched_skills") if isinstance(ats_result, dict) else None,
        ),
        "missing_skills": _first_non_empty(
            application.get("missing_skills"),
            ats_result.get("missing_skills") if isinstance(ats_result, dict) else None,
        ),
        "resume_text": resume_text[:12000],
    }


def _generate_rule_based_questions(application: dict) -> list[dict]:
    context = _build_resume_context(application)
    skills = _string_list(context.get("skills"))
    projects = _string_list(context.get("projects"))
    resume_text = str(context.get("resume_text") or "")
    job_title = context.get("job_title") or "the role"
    required_skills = _string_list(context.get("required_skills"))
    common_skills = _string_list(context.get("common_skills"))
    missing_skills = _string_list(context.get("missing_skills"))
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
    primary_skill = _pick_first(common_skills or required_skills or skills, ["FastAPI", "React", "Python"])
    secondary_skill = _pick_first([skill for skill in (common_skills or required_skills) if skill != primary_skill], ["deployment"])
    missing_skill = _pick_first(missing_skills, ["a missing required skill"])

    return [
        _question(
            "q1",
            "Project + Job Skill",
            "Easy",
            f"Your resume mentions {primary_project}. How does that project show readiness for the {job_title} role, especially around {primary_skill}?",
            "Project relevance, job-skill alignment, ownership",
            primary_skill,
            primary_project,
        ),
        _question(
            "q2",
            "Project + Job Skill",
            "Easy",
            f"This role requires {secondary_skill}. Where did you apply similar engineering decisions in {skill_project}, and what trade-offs did you make?",
            "Project clarity, required skill application, implementation trade-offs",
            secondary_skill,
            skill_project,
        ),
        _question(
            "q3",
            "Skill-Based Technical",
            "Medium",
            _build_skill_question(skill_project, primary_skill, job_title),
            "Technical correctness, model or framework knowledge, practical depth",
            primary_skill,
            skill_project,
        ),
        _question(
            "q4",
            "System Design / Debugging",
            "Medium",
            f"For the {job_title} role, how would you make {system_project} maintainable, secure, and deployable in production?",
            "Architecture, security, deployment, maintainability",
            secondary_skill,
            system_project,
        ),
        _question(
            "q5",
            "Required Skill Gap / Learning",
            "Hard",
            f"If this role needs {missing_skill} and your resume shows limited direct evidence of it, how would you learn and integrate it into one of your existing projects?",
            "Learning ability, gap handling, practical integration plan",
            missing_skill,
            primary_project,
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
                "job_skill": str(item.get("job_skill") or "").strip(),
                "resume_evidence": str(item.get("resume_evidence") or "").strip(),
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
    job_skill: str = "",
    resume_evidence: str = "",
) -> dict:
    return {
        "id": question_id,
        "category": category,
        "difficulty": difficulty,
        "question": question,
        "expected_focus": expected_focus,
        "job_skill": job_skill,
        "resume_evidence": resume_evidence,
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


def _build_skill_question(skill_project: str, primary_skill: str, job_title: str = "the role") -> str:
    if "efficientnet" in skill_project.lower() or "vehicle damage" in skill_project.lower():
        return f"For the {job_title} role, how would you explain the process of training your EfficientNetB0 model for vehicle damage detection using transfer learning?"

    return f"How have you applied {primary_skill} in {skill_project}, and what technical trade-offs matter for the {job_title} role?"


def _common_skills(required_skills: list[str], resume_skills: list[str], projects: list[str], resume_text: str) -> list[str]:
    search_text = " ".join(resume_skills + projects + [resume_text]).lower()
    common = []

    for skill in required_skills:
        if skill and skill.lower() in search_text:
            common.append(skill)

    return common


def _candidate_highlights(resume_text: str) -> list[str]:
    highlights = []

    for line in str(resume_text or "").splitlines():
        clean_line = line.strip()

        if not clean_line:
            continue

        lower = clean_line.lower()

        if any(term in lower for term in ("project", "platform", "intern", "fastapi", "react", "python", "fraud", "classifier", "deployment")):
            highlights.append(clean_line)

        if len(highlights) >= 12:
            break

    return highlights
