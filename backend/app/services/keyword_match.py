import re


SKILL_ALIASES = {
    "c++": ["c++", "cpp", "c plus plus"],
    "c#": ["c#", "c sharp"],
    "java": ["java"],
    "javascript": ["javascript", "java script", "js"],
    "python": ["python"],
    "flask": ["flask"],
    "fastapi": ["fastapi", "fast api"],
    "mongodb": ["mongodb", "mongo db"],
    "sql": ["sql", "mysql", "postgresql", "postgre sql", "sqlite"],
    "ai": ["ai", "artificial intelligence"],
    "ml": ["ml", "machine learning"],
    "opencv": ["opencv", "open cv"],
    "paddleocr": ["paddleocr", "paddle ocr"],
    "pytorch": ["pytorch", "py torch"],
    "tensorflow": ["tensorflow", "tensor flow"],
    "keras": ["keras"],
    "scikit-learn": ["scikit-learn", "scikit learn", "sklearn"],
    "react": ["react", "reactjs", "react.js"],
    "node.js": ["node.js", "nodejs", "node js"],
    "rest api": ["rest api", "rest apis", "restful api", "rest"],
}

_SEPARATOR_PATTERN = re.compile(r"[/|,;\n\r\t]+")
_SPACE_PATTERN = re.compile(r"\s+")
_ALNUM_SPACE_PATTERN = re.compile(r"[^a-z0-9+#.\-\s]+")
_SIMPLIFY_PATTERN = re.compile(r"[^a-z0-9#]+")


def normalize_text(text: str) -> str:
    text = str(text or "").lower()
    text = _SEPARATOR_PATTERN.sub(" ", text)
    text = _ALNUM_SPACE_PATTERN.sub(" ", text)
    return _SPACE_PATTERN.sub(" ", text).strip()


def simplify_text(text: str) -> str:
    text = normalize_text(text)
    text = text.replace("+", " plus ")
    text = text.replace("#", " sharp ")
    text = text.replace(".", " ")
    text = text.replace("-", " ")
    text = _SIMPLIFY_PATTERN.sub(" ", text)
    return _SPACE_PATTERN.sub(" ", text).strip()


def skill_present(skill: str, resume_text: str, extracted_skills: list[str] | None = None) -> bool:
    searchable_text = _build_searchable_text(resume_text, extracted_skills)
    normalized = normalize_text(searchable_text)
    simplified = simplify_text(searchable_text)

    for alias in _aliases_for_skill(skill):
        if _alias_present(alias, normalized, simplified):
            return True

    return False


def calculate_skill_match(
    resume_text_or_skills,
    required_skills,
    extracted_skills: list[str] | None = None,
):
    if isinstance(resume_text_or_skills, list) and extracted_skills is None:
        resume_text = ""
        extracted_skills = resume_text_or_skills
    else:
        resume_text = str(resume_text_or_skills or "")
        extracted_skills = extracted_skills or []

    required_skills = required_skills or []
    matched = []
    missing = []

    for skill in required_skills:
        if skill_present(skill, resume_text, extracted_skills):
            matched.append(skill)
        else:
            missing.append(skill)

    score = round((len(matched) / len(required_skills)) * 100) if required_skills else 0

    normalized_preview = normalize_text(_build_searchable_text(resume_text, extracted_skills))[:500]
    print("\n========== ATS SKILL MATCH DEBUG ==========")
    print("REQUIRED SKILLS:", required_skills)
    print("MATCHED SKILLS:", matched)
    print("MISSING SKILLS:", missing)
    print("NORMALIZED RESUME PREVIEW:", normalized_preview)
    print("===========================================\n")

    return {
        "score": score,
        "ats_score": score,
        "matched_skills": matched,
        "missing_skills": missing,
    }


def _build_searchable_text(resume_text: str, extracted_skills: list[str] | None) -> str:
    skill_text = " ".join(_stringify_skill(skill) for skill in (extracted_skills or []))
    return f"{resume_text or ''} {skill_text}".strip()


def _stringify_skill(skill) -> str:
    if isinstance(skill, dict):
        return " ".join(str(value) for value in skill.values() if value is not None)

    return str(skill or "")


def _aliases_for_skill(skill: str) -> list[str]:
    canonical = normalize_text(skill)
    simplified_canonical = simplify_text(skill)
    aliases = [canonical, simplified_canonical]
    aliases.extend(SKILL_ALIASES.get(canonical, []))
    aliases.extend(SKILL_ALIASES.get(simplified_canonical, []))

    deduped = []
    seen = set()

    for alias in aliases:
        alias = normalize_text(alias)

        if alias and alias not in seen:
            deduped.append(alias)
            seen.add(alias)

    return deduped


def _alias_present(alias: str, normalized_text: str, simplified_resume_text: str) -> bool:
    normalized_alias = normalize_text(alias)
    simplified_alias = simplify_text(alias)

    if _safe_contains(normalized_text, normalized_alias):
        return True

    if simplified_alias != normalized_alias and _safe_contains(simplified_resume_text, simplified_alias):
        return True

    return False


def _safe_contains(text: str, alias: str) -> bool:
    if not alias:
        return False

    escaped_parts = [re.escape(part) for part in alias.split()]
    pattern = r"\s+".join(escaped_parts)
    regex = rf"(?<![a-z0-9]){pattern}(?![a-z0-9])"
    return re.search(regex, text) is not None
