import re
from pathlib import Path

import fitz


SECTION_HEADERS = {
    "education": "education",
    "skills": "skills",
    "technical skills": "skills",
    "projects": "projects",
    "academic projects": "projects",
    "experience": "experience",
    "work experience": "experience",
    "internship": "experience",
    "internships": "experience",
    "certifications": "certifications",
    "certificates": "certifications",
    "activities": None,
    "achievements": None,
    "find me online": None,
}

TECHNOLOGY_KEYWORDS = [
    "Python",
    "C++",
    "Java",
    "JavaScript",
    "React",
    "FastAPI",
    "Flask",
    "MongoDB",
    "SQL",
    "HTML",
    "CSS",
    "Node.js",
    "NumPy",
    "pandas",
    "PyTorch",
    "TensorFlow",
    "OpenCV",
    "scikit-learn",
    "Git",
    "Linux",
    "Matplotlib",
    "Keras",
    "HuggingFace",
    "OCR",
    "ELA",
    "MVSS",
    "TruFor",
]

DATE_PATTERN = re.compile(
    r"\b(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|"
    r"aug|august|sep|sept|september|oct|october|nov|november|dec|december)\s+\d{4}"
    r"\s*(?:-|to|present)?\s*(?:present|\d{4}|"
    r"(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|"
    r"aug|august|sep|sept|september|oct|october|nov|november|dec|december)\s+\d{4})?"
    r"\b|\bgraduated\s+\d{4}\b|\b\d{4}\s*(?:-|to)\s*(?:present|\d{4})\b|\b\d{4}\b",
    re.IGNORECASE,
)

DEGREE_PATTERN = re.compile(
    r"\b(?:"
    r"b\.?\s*tech(?:\s+[a-z.() ]+)?|"
    r"b\.?\s*e\.?(?:\s+[a-z.() ]+)?|"
    r"m\.?\s*tech(?:\s+[a-z.() ]+)?|"
    r"b\.?\s*sc(?:\s+[a-z.() ]+)?|"
    r"m\.?\s*sc(?:\s+[a-z.() ]+)?|"
    r"mba(?:\s+[a-z.() ]+)?|"
    r"mca(?:\s+[a-z.() ]+)?|"
    r"cbse\s+xii(?:\s+[a-z.() ]+)?|"
    r"cbse\s+x(?:\s+[a-z.() ]+)?|"
    r"class\s+xii(?:\s+[a-z.() ]+)?|"
    r"class\s+x(?:\s+[a-z.() ]+)?|"
    r"computer science"
    r")\b",
    re.IGNORECASE,
)

INSTITUTION_PATTERN = re.compile(
    r"\b(?:institute|university|college|school|academy|nitc|national institute of technology calicut)\b",
    re.IGNORECASE,
)

GRADE_PATTERN = re.compile(
    r"\b(?:cgpa|gpa|grade|percentage|percent|marks?)\b|"
    r"\b\d+(?:\.\d+)?\s*/\s*(?:10|100)\b|\b\d+(?:\.\d+)?%",
    re.IGNORECASE,
)

LINK_PATTERN = re.compile(r"\b(?:github|https?://|www\.)\b", re.IGNORECASE)
BULLET_PATTERN = re.compile(r"^[-*•]\s*")


def extract_text_from_pdf(file_path: str):
    document = fitz.open(file_path)
    page_text = []

    try:
        for page in document:
            page_text.append(_extract_ordered_page_text(page))

        return {
            "text": normalize_text("\n".join(page_text)),
            "total_pages": document.page_count,
        }
    finally:
        document.close()


def _extract_ordered_page_text(page):
    text_dict = page.get_text("dict")
    left_column = []
    right_column = []
    full_width_top = []
    page_width = page.rect.width
    column_split = page_width * 0.56

    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue

        block_lines = []
        for line in block.get("lines", []):
            spans = sorted(line.get("spans", []), key=lambda span: span.get("bbox", [0])[0])
            text = " ".join(span.get("text", "") for span in spans)
            text = normalize_text(text)
            if text:
                bbox = line.get("bbox", block.get("bbox", [0, 0, 0, 0]))
                block_lines.append((bbox[1], bbox[0], text))

        if not block_lines:
            continue

        bbox = block.get("bbox", [0, 0, 0, 0])
        block_entry = (
            bbox[1],
            bbox[0],
            [text for _y, _x, text in sorted(block_lines, key=lambda item: (round(item[0], 1), item[1]))],
        )

        if bbox[1] < 125 and bbox[0] < column_split:
            full_width_top.append(block_entry)
        elif bbox[0] >= column_split:
            right_column.append(block_entry)
        else:
            left_column.append(block_entry)

    ordered_lines = []
    for column in [full_width_top, left_column, right_column]:
        for _y, _x, block_lines in sorted(column, key=lambda item: (round(item[0], 1), item[1])):
            ordered_lines.extend(block_lines)

    return "\n".join(ordered_lines)


def normalize_text(text):
    replacements = {
        "\r": "\n",
        "\t": " ",
        "\u00a0": " ",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "â€“": "-",
        "â€”": "-",
        "â€¢": "•",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[ \f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_text(text: str):
    return normalize_text(text)


def extract_candidate_name(text: str) -> str:
    for line in get_clean_lines(text):
        if _looks_like_candidate_name(line):
            return line
    return ""


def extract_resume_photo(file_path: str, output_dir: str) -> dict:
    output_path = None
    document = fitz.open(file_path)

    try:
        for page_index in range(document.page_count):
            page = document[page_index]
            for image_index, image in enumerate(page.get_images(full=True)):
                xref = image[0]
                image_info = document.extract_image(xref)
                image_bytes = image_info.get("image")
                extension = image_info.get("ext", "png")

                if not image_bytes or len(image_bytes) < 5000:
                    continue

                output_directory = Path(output_dir)
                output_directory.mkdir(parents=True, exist_ok=True)
                output_path = output_directory / f"resume_photo_page_{page_index + 1}_{image_index + 1}.{extension}"
                output_path.write_bytes(image_bytes)
                return {
                    "available": True,
                    "path": str(output_path),
                    "message": "Resume photo extracted",
                }
    finally:
        document.close()

    return {
        "available": False,
        "path": None,
        "message": "Resume photo not found",
    }


def get_clean_lines(text):
    lines = []
    previous_line = None

    for line in normalize_text(text).splitlines():
        cleaned_line = _strip_bullet(line.strip())
        if not cleaned_line:
            continue
        if cleaned_line == previous_line:
            continue
        lines.append(cleaned_line)
        previous_line = cleaned_line

    return lines


def is_section_header(line):
    normalized = _normalize_header(line)
    return SECTION_HEADERS.get(normalized, False) if normalized in SECTION_HEADERS else False


def extract_sections(text: str):
    sections = {
        "education": [],
        "skills": [],
        "projects": [],
        "experience": [],
        "certifications": [],
    }

    current_section = None
    lines = merge_wrapped_lines(get_clean_lines(text))
    print("\n===== CLEAN LINES =====")
    for line in lines[:100]:
        print(line)
    print("=======================\n")
    for line in lines:
        normalized_header = _normalize_header(line)
        if normalized_header in SECTION_HEADERS:
            current_section = SECTION_HEADERS[normalized_header]
            continue

        if _is_noise_line(line):
            continue

        if current_section in sections:
            sections[current_section].append(line)

    raw_sections = {
        name: clean_text("\n".join(section_lines))
        for name, section_lines in sections.items()
    }

    return {
        "education": {
            "raw_text": raw_sections["education"],
            "items": parse_education(raw_sections["education"]),
        },
        "skills": {
            "raw_text": raw_sections["skills"],
            "items": parse_skills(raw_sections["skills"]),
        },
        "projects": {
            "raw_text": raw_sections["projects"],
            "items": parse_projects(raw_sections["projects"]),
        },
        "experience": {
            "raw_text": raw_sections["experience"],
            "items": parse_experience(raw_sections["experience"]),
        },
        "certifications": {
            "raw_text": raw_sections["certifications"],
            "items": parse_certifications(raw_sections["certifications"]),
        },
    }


def merge_wrapped_lines(lines):
    merged_lines = []

    for line in lines:
        if not merged_lines:
            merged_lines.append(line)
            continue

        if _starts_new_logical_line(line):
            merged_lines.append(line)
            continue

        previous_line = merged_lines[-1]
        if _should_merge_with_previous(previous_line, line):
            merged_lines[-1] = f"{previous_line} {line}".strip()
        else:
            merged_lines.append(line)

    return merged_lines


def parse_experience(experience_text: str):
    lines = merge_wrapped_lines(get_clean_lines(experience_text))
    entries = []
    current_entry = None

    for line in lines:
        if _looks_like_experience_heading(line):
            if current_entry:
                entries.append(_finish_experience_entry(current_entry))
            current_entry = {
                "heading": line,
                "duration": "",
                "body": [],
            }
            continue

        if not current_entry:
            current_entry = {
                "heading": line,
                "duration": "",
                "body": [],
            }
            continue

        if not current_entry["duration"] and _is_duration_line(line):
            current_entry["duration"] = line
        else:
            current_entry["body"].append(line)

    if current_entry:
        entries.append(_finish_experience_entry(current_entry))

    return entries


def parse_education(education_text: str):
    lines = _normalize_education_lines(get_clean_lines(education_text))
    degree_indexes = [index for index, line in enumerate(lines) if _is_degree_line(line)]

    if not degree_indexes:
        return []

    items = []
    for index, degree_index in enumerate(degree_indexes):
        previous_degree_index = degree_indexes[index - 1] if index > 0 else -1
        next_degree_index = degree_indexes[index + 1] if index + 1 < len(degree_indexes) else len(lines)
        context_lines = lines[previous_degree_index + 1:next_degree_index]
        degree_line = lines[degree_index]

        if _has_school_board_degree(degree_line):
            school = _find_school_institution(lines, degree_index) or _find_institution_in_context(context_lines)
            duration = _find_graduation_duration(lines, degree_index)
            school_entries = extract_school_board_entries(degree_line, school, duration)

            if school_entries:
                nearby_school_grade = _find_school_grade(lines[degree_index:next_degree_index])
                for school_entry in school_entries:
                    if not school_entry["description"]:
                        school_entry["description"] = nearby_school_grade
                    school_entry["raw_text"] = _build_education_raw_text(school_entry)
                items.extend(school_entries)
                continue

            degree = clean_degree_name(_extract_degree(degree_line))
            description = _find_school_grade(context_lines)
        else:
            degree = clean_degree_name(_extract_degree(degree_line))
            institution = _find_institution_in_context(context_lines)
            duration = _find_college_duration(context_lines)
            description = _find_college_grade(context_lines)

            items.append(
                {
                    "title": degree,
                    "institution": institution,
                    "degree": degree,
                    "duration": duration,
                    "description": description,
                    "raw_text": _build_education_raw_text(
                        {
                            "institution": institution,
                            "duration": duration,
                            "degree": degree,
                            "description": description,
                        }
                    ),
                }
            )
            continue

        items.append(
            {
                "title": degree,
                "institution": school,
                "degree": degree,
                "duration": duration,
                "description": description,
                "raw_text": _build_education_raw_text(
                    {
                        "institution": school,
                        "duration": duration,
                        "degree": degree,
                        "description": description,
                    }
                ),
            }
        )

    return _dedupe_education_items(items)


def parse_projects(projects_text: str):
    lines = [line for line in merge_wrapped_lines(get_clean_lines(projects_text)) if not _is_noise_line(line)]
    projects = []
    current_project = None

    for line in lines:
        if _looks_like_project_title(line):
            if current_project:
                projects.append(_finish_project(current_project))
            current_project = {
                "title": _clean_project_title(line),
                "body": [],
            }
            continue

        if not current_project:
            current_project = {
                "title": _clean_project_title(line),
                "body": [],
            }
        else:
            current_project["body"].append(line)

    if current_project:
        projects.append(_finish_project(current_project))

    return projects


def parse_skills(skills_text: str):
    if not skills_text:
        return []

    lines = get_clean_lines(skills_text)
    skills = []
    seen = set()

    for line in lines:
        line = re.sub(r"^[A-Za-z ]+:\s*", "", line).strip()
        parts = re.split(r"[,|/;•\n]+", line)

        for part in parts:
            skill = part.strip(" -:")
            if not skill or _normalize_header(skill) in SECTION_HEADERS:
                continue
            if len(skill.split()) > 6:
                continue

            key = skill.lower()
            if key not in seen:
                skills.append(skill)
                seen.add(key)

    return skills


def parse_certifications(certifications_text: str):
    certifications = []
    for line in get_clean_lines(certifications_text):
        if _normalize_header(line) in {"activities", "achievements"}:
            break
        certifications.append(line)
    return certifications


def _is_noise_line(line):
    normalized = _normalize_header(line)
    return bool(
        normalized in {"powered by", "find me online", "sp"}
        or "enhancv.com" in line.lower()
        or "@" in line
        or (not _is_duration_line(line) and re.search(r"\+?\d[\d\s-]{7,}", line))
        or line.strip() == "\u200b"
    )


def _finish_experience_entry(entry):
    title, company = _split_title_company(entry["heading"])
    bullets = [_strip_bullet(line) for line in entry["body"] if line]

    if not company and bullets and _looks_like_company_line(bullets[0]):
        company = bullets.pop(0)

    description = clean_text("\n".join(bullets))
    raw_text = clean_text("\n".join([entry["heading"], entry["duration"], *bullets]))

    return {
        "title": title,
        "company": company,
        "duration": entry["duration"],
        "description": description,
        "bullets": bullets,
        "technologies": _detect_technologies(raw_text),
        "raw_text": raw_text,
    }


def _finish_project(project):
    body_lines = [_strip_bullet(line) for line in project["body"] if line]
    raw_text = clean_text("\n".join([project["title"], *body_lines]))
    links = [line for line in body_lines if LINK_PATTERN.search(line)]
    bullets = [line for line in body_lines if not LINK_PATTERN.search(line)]

    return {
        "title": project["title"],
        "description": clean_text("\n".join(bullets)),
        "bullets": bullets,
        "technologies": _detect_technologies(raw_text),
        "links": links,
        "raw_text": raw_text,
    }


def _split_title_company(heading):
    for separator in [",", " - ", " | "]:
        if separator in heading:
            title, company = heading.split(separator, 1)
            return title.strip(), company.strip()
    return heading.strip(), ""


def _looks_like_experience_heading(line):
    lowered = line.lower()
    if is_section_header(line) or _is_duration_line(line) or _is_bullet_line(line):
        return False
    if len(line.split()) > 10:
        return False
    if re.match(r"^(and|or|with|using|generation|analysis)\b", lowered):
        return False

    role_words = {"intern", "developer", "engineer", "analyst", "lead", "member", "club", "gdsc"}
    return any(word in lowered for word in role_words)


def _looks_like_project_title(line):
    if is_section_header(line) or _is_duration_line(line) or _is_bullet_line(line):
        return False
    if LINK_PATTERN.search(line):
        return False
    if len(line.split()) > 12:
        return False
    if re.match(r"^(and|or|with|using|generation|analysis)\b", line.lower()):
        return False

    has_parenthesized_tech = bool(
        re.search(
            r"\([^)]*(python|react|c\+\+|java|sql|fastapi|numpy|pandas|pytorch|tensorflow|opencv|flask)[^)]*\)",
            line,
            re.IGNORECASE,
        )
    )
    title_case_words = sum(1 for word in line.split() if word[:1].isupper() or any(char.isdigit() for char in word))
    return has_parenthesized_tech or title_case_words >= max(1, len(line.split()) - 1)


def _looks_like_company_line(line):
    if is_section_header(line) or _is_duration_line(line):
        return False
    if len(line.split()) > 6:
        return False

    company_words = {"novac", "nit", "nitc", "calicut", "google", "gdsc", "company", "labs"}
    lowered = line.lower()
    return line.isupper() or any(word in lowered for word in company_words)


def _clean_project_title(line):
    return re.sub(r"\s*github\s*$", "", line, flags=re.IGNORECASE).strip(" -")


def extract_school_board_entries(line, current_school, current_duration):
    entries = []
    raw_line = clean_text(line)
    parts = re.split(r"\s+-\s+(?=(?:CBSE|Class|XII|X)\b)", raw_line, flags=re.IGNORECASE)

    for part in parts:
        match = re.match(
            r"^\s*(?P<degree>(?:CBSE\s+XII|Class\s+XII|XII|CBSE\s+X|Class\s+X|X)"
            r"(?:\s*\([^)]+\)|(?:\s+[A-Za-z]+){0,4})?)\s*:?\s*"
            r"(?P<grade>\d+(?:\.\d+)?%)?\s*$",
            part.strip(),
            re.IGNORECASE,
        )
        if not match:
            continue

        degree = clean_degree_name(match.group("degree"))
        grade = extract_grade(match.group("grade") or part)

        entries.append(
            {
                "title": degree,
                "institution": current_school,
                "degree": degree,
                "duration": current_duration,
                "description": grade,
                "raw_text": raw_line,
            }
        )

    return entries


def extract_grade(line):
    if not line:
        return ""

    percentage_match = re.search(r"\b\d+(?:\.\d+)?%", line)
    if percentage_match:
        return percentage_match.group(0)

    cgpa_match = re.search(r"\bCGPA\s*:?\s*\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?", line, re.IGNORECASE)
    if cgpa_match:
        return re.sub(r"\s+", " ", cgpa_match.group(0)).replace("CGPA ", "CGPA: ")

    score_match = re.search(r"\b\d+(?:\.\d+)?\s*/\s*(?:10|100)\b", line)
    if score_match:
        return score_match.group(0)

    return ""


def clean_degree_name(text):
    text = re.sub(r":.*$", "", text or "").strip()
    text = text.replace("(", " ").replace(")", " ")
    text = re.sub(r"\s+", " ", text).strip(" -:")

    replacements = {
        "xii": "XII",
        "x": "X",
        "cbse": "CBSE",
        "class": "Class",
        "b.tech": "B.Tech",
        "b.e": "B.E",
        "m.tech": "M.Tech",
    }

    words = []
    for word in text.split():
        key = word.lower().strip(".")
        if key in replacements:
            words.append(replacements[key])
        else:
            words.append(word)

    return " ".join(words)


def _has_school_board_degree(line):
    return bool(re.search(r"\b(?:CBSE\s+XII|Class\s+XII|XII|CBSE\s+X|Class\s+X|X)\b", line, re.IGNORECASE))


def _find_school_institution(lines, degree_index):
    for index in range(degree_index - 1, -1, -1):
        line = lines[index]
        if _is_institution_line(line) and re.search(r"\bschool\b", line, re.IGNORECASE):
            return line
        if _is_degree_line(line) and not _has_school_board_degree(line):
            break

    for index in range(degree_index + 1, len(lines)):
        line = lines[index]
        if _is_institution_line(line) and re.search(r"\bschool\b", line, re.IGNORECASE):
            return line
        if _is_degree_line(line):
            break

    return ""


def _find_graduation_duration(lines, degree_index):
    for index in range(degree_index - 1, -1, -1):
        line = lines[index]
        if re.search(r"\bgraduated\s+\d{4}\b", line, re.IGNORECASE):
            return line
        if _is_degree_line(line) and not _has_school_board_degree(line):
            break

    for index in range(degree_index + 1, len(lines)):
        line = lines[index]
        if re.search(r"\bgraduated\s+\d{4}\b", line, re.IGNORECASE):
            return line
        if _is_degree_line(line):
            break

    return ""


def _find_school_grade(lines):
    for line in lines:
        if "cgpa" in line.lower():
            continue
        grade = extract_grade(line)
        if grade and grade.endswith("%"):
            return grade
    return ""


def _find_college_grade(lines):
    for line in lines:
        if "cgpa" in line.lower():
            grade = extract_grade(line)
            if grade:
                return grade

    for line in lines:
        grade = extract_grade(line)
        if grade and not grade.endswith("%"):
            return grade

    return ""


def _dedupe_education_items(items):
    deduped_items = []
    seen = set()

    for item in items:
        key = (
            item.get("degree", "").lower(),
            item.get("institution", "").lower(),
            item.get("duration", "").lower(),
            item.get("description", "").lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped_items.append(item)

    return deduped_items


def _build_education_raw_text(item):
    return clean_text(
        "\n".join(
            value
            for value in [
                item.get("institution", ""),
                item.get("duration", ""),
                item.get("degree", ""),
                item.get("description", ""),
            ]
            if value
        )
    )


def _normalize_education_lines(lines):
    normalized = []
    index = 0

    while index < len(lines):
        line = lines[index]

        if _is_degree_line(line):
            parts = [line]
            while index + 1 < len(lines) and _is_degree_continuation(" ".join(parts), lines[index + 1]):
                index += 1
                parts.append(lines[index])
            normalized.append(" ".join(parts))
            index += 1
            continue

        school_score_match = re.search(r"\s+%\s*/?\s*$", line)
        if _is_institution_line(line) and school_score_match:
            normalized.append(line[:school_score_match.start()].strip())
            if index + 1 < len(lines) and re.match(r"^\d+(?:\.\d+)?$", lines[index + 1]):
                normalized.append(f"{lines[index + 1]}%")
                index += 3 if index + 2 < len(lines) and re.match(r"^\d+(?:\.\d+)?$", lines[index + 2]) else 2
            else:
                index += 1
            continue

        if _is_institution_line(line):
            parts = [line]
            while index + 1 < len(lines) and _is_institution_continuation(lines[index + 1]):
                index += 1
                parts.append(lines[index])
            normalized.append(" ".join(parts))
            index += 1
            continue

        if re.match(r"^cgpa\b", line, re.IGNORECASE) and extract_grade(line):
            normalized.append(line)
            index += 1
            continue

        if re.match(r"^cgpa\b", line, re.IGNORECASE) and index + 2 < len(lines):
            if index + 3 < len(lines) and lines[index + 1].strip() == "/":
                normalized.append(f"CGPA: {lines[index + 2]}/{lines[index + 3]}")
                index += 4
            elif re.match(r"^\d+(?:\.\d+)?$", lines[index + 1]) and re.match(r"^\d+(?:\.\d+)?$", lines[index + 2]):
                normalized.append(f"CGPA: {lines[index + 1]}/{lines[index + 2]}")
                index += 3
            else:
                normalized.append(line)
                index += 1
            continue

        if re.match(r"^%\s*/?$", line) and index + 1 < len(lines):
            if index + 2 < len(lines) and lines[index + 1].strip() == "/":
                normalized.append(f"{lines[index + 2]}%")
                index += 4 if index + 3 < len(lines) and re.match(r"^\d", lines[index + 3]) else 3
            else:
                normalized.append(f"{lines[index + 1]}%")
                index += 3 if index + 2 < len(lines) and re.match(r"^\d", lines[index + 2]) else 2
            continue

        normalized.append(line)
        index += 1

    return normalized


def _extract_degree(line):
    line = line.strip(" -:")
    score_match = GRADE_PATTERN.search(line)
    if score_match:
        before_score = line[:score_match.start()].strip(" -:")
        after_score = line[score_match.end():].strip(" -:")
        if _is_degree_line(after_score):
            return after_score
        if _is_degree_line(before_score):
            return before_score
    return line


def _find_institution_in_context(lines):
    for line in lines:
        if _is_institution_line(line):
            return line
    return ""


def _find_duration_in_context(lines):
    for line in lines:
        if _is_duration_line(line):
            return line
    return ""


def _find_college_duration(lines):
    for line in lines:
        if re.search(r"\bgraduated\s+\d{4}\b", line, re.IGNORECASE):
            continue
        if _is_duration_line(line):
            return line
    return ""


def _build_education_description(lines, degree, institution, duration):
    description_lines = []
    for line in lines:
        if line in {degree, institution, duration}:
            continue
        if _is_degree_line(line) or _is_institution_line(line) or _is_duration_line(line):
            continue
        if GRADE_PATTERN.search(line) or line:
            description_lines.append(line)
    return clean_text("\n".join(description_lines))


def _starts_new_logical_line(line):
    if line.strip().startswith("("):
        return False

    return bool(
        is_section_header(line)
        or _is_bullet_line(line)
        or _is_duration_line(line)
        or _is_degree_line(line)
        or _is_institution_line(line)
        or _looks_like_experience_heading(line)
        or _looks_like_project_title(line)
        or LINK_PATTERN.search(line)
    )


def _should_merge_with_previous(previous_line, line):
    if not previous_line:
        return False
    if previous_line.endswith((".", ":", ";")) and not re.match(r"^(and|or|with|using)\b", line.lower()):
        return False
    if len(line.split()) <= 4:
        return True
    return bool(re.match(r"^(and|or|with|using|metadata|generation|analysis)\b", line.lower()))


def _is_duration_line(line):
    return bool(DATE_PATTERN.search(line))


def _is_degree_line(line):
    return bool(DEGREE_PATTERN.search(line))


def _is_institution_line(line):
    return bool(INSTITUTION_PATTERN.search(line))


def _is_bullet_line(line):
    return bool(BULLET_PATTERN.match(line.strip()))


def _is_degree_continuation(current_line, next_line):
    if _is_degree_line(next_line) or _is_institution_line(next_line) or _is_duration_line(next_line):
        return False
    if GRADE_PATTERN.search(next_line) or next_line == "%":
        return False

    has_unclosed_parenthesis = current_line.count("(") > current_line.count(")")
    degree_words = {"engineering", "science", "computer", "mechanical", "technology"}
    next_words = set(re.findall(r"[a-z]+", next_line.lower()))
    return has_unclosed_parenthesis or bool(next_words & degree_words)


def _is_institution_continuation(line):
    if _is_degree_line(line) or _is_duration_line(line) or GRADE_PATTERN.search(line) or line == "%":
        return False
    return bool(
        line.startswith("(")
        or re.search(r"\b(?:technology|calicut|nitc|public)\b", line, re.IGNORECASE)
    )


def _detect_technologies(text):
    technologies = []
    for technology in TECHNOLOGY_KEYWORDS:
        pattern = re.escape(technology)
        if re.search(rf"(?<!\w){pattern}(?!\w)", text, re.IGNORECASE):
            technologies.append(technology)
    return technologies


def _normalize_header(line):
    line = _strip_bullet(line).rstrip(":").lower()

    line = re.sub(r"[^a-z ]", "", line)

    line = re.sub(r"\s+", " ", line).strip()

    words = line.split()

    if len(words) >= 2:
        reconstructed = "".join(words)

        known_headers = {
            "education",
            "technicalskills",
            "skills",
            "experience",
            "projects",
            "certifications",
            "achievements",
            "leadership",
        }

        if reconstructed in known_headers:
            return reconstructed.replace(
                "technicalskills",
                "technical skills"
            )

    return line

def _strip_bullet(line):
    return BULLET_PATTERN.sub("", line.strip()).strip()


def _looks_like_candidate_name(line):
    if not line or len(line.split()) > 5:
        return False
    if any(char.isdigit() for char in line):
        return False
    if "@" in line or LINK_PATTERN.search(line):
        return False

    blocked = {
        "education",
        "skills",
        "projects",
        "experience",
        "certifications",
        "resume",
        "find me online",
    }
    if _normalize_header(line) in blocked:
        return False

    return bool(re.search(r"[A-Za-z]{2,}", line))
