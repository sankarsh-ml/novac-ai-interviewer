import re
from pathlib import Path
from datetime import datetime

import fitz


SECTION_HEADERS = {
    "education": "education",
    "academics": "education",
    "academic background": "education",
    "skills": "skills",
    "technical skills": "skills",
    "technologies": "skills",
    "projects": "projects",
    "academic projects": "projects",
    "personal projects": "projects",
    "experience": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "internship": "experience",
    "internships": "experience",
    "certifications": "certifications",
    "certificates": "certifications",
    # stop sections
    "activities": None,
    "achievements": None,
    "achievement": None,
    "leadership": None,
    "achievements leadership": None,
    "achievements and leadership": None,
    "positions of responsibility": None,
    "extracurricular": None,
    "extracurriculars": None,
    "find me online": None,
}

COMPACT_SECTION_HEADERS = {key.replace(" ", ""): value for key, value in SECTION_HEADERS.items()}
COMPACT_CANONICAL_HEADERS = {key.replace(" ", ""): key for key in SECTION_HEADERS}
COMPACT_CANONICAL_HEADERS.update({
    "technicalskill": "technical skills",
    "technicalskills": "technical skills",
    "workexperiences": "work experience",
    "professionalexperiences": "professional experience",
    "academicproject": "academic projects",
    "academicprojects": "academic projects",
    "achievementleadership": "achievements leadership",
    "achievementsleadership": "achievements leadership",
    "achievementsandleadership": "achievements and leadership",
})
COMPACT_SECTION_HEADERS.update({
    "technicalskill": "skills",
    "technicalskills": "skills",
    "workexperiences": "experience",
    "professionalexperiences": "experience",
    "academicproject": "projects",
    "academicprojects": "projects",
    "achievementleadership": None,
    "achievementsleadership": None,
    "achievementsandleadership": None,
})

TECHNOLOGY_KEYWORDS = [
    "Python", "C++", "Java", "JavaScript", "TypeScript", "React", "React.js",
    "FastAPI", "Flask", "Django", "MongoDB", "SQL", "MySQL", "PostgreSQL",
    "HTML", "CSS", "Node.js", "Express", "NumPy", "pandas", "PyTorch",
    "TensorFlow", "Keras", "OpenCV", "scikit-learn", "Scikit-learn", "Git",
    "GitHub", "Linux", "Matplotlib", "HuggingFace", "Hugging Face", "OCR",
    "PaddleOCR", "ELA", "MVSS", "TruFor", "EfficientNet", "MobileNetV2",
    "CNN", "CNNs", "NLP", "REST APIs", "Pydantic", "Jupyter", "Colab",
    "Roboflow",
]

MONTH_PATTERN = (
    r"jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|"
    r"aug|august|sep|sept|september|oct|october|nov|november|dec|december"
)

DATE_RANGE_PATTERN = re.compile(
    rf"\b(?:{MONTH_PATTERN})\s+\d{{4}}\s*(?:-|to)\s*(?:present|(?:{MONTH_PATTERN})\s+\d{{4}})\b"
    r"|\b\d{4}\s*(?:-|to)\s*(?:present|\d{4})\b",
    re.IGNORECASE,
)

ANY_DATE_PATTERN = re.compile(
    rf"\b(?:{MONTH_PATTERN})\s+\d{{4}}\b|\bgraduated\s+\d{{4}}\b|\b\d{{4}}\b",
    re.IGNORECASE,
)

DEGREE_PATTERN = re.compile(
    r"\b(?:"
    r"b\.?\s*tech|b\.?\s*e\.?|m\.?\s*tech|b\.?\s*sc|m\.?\s*sc|"
    r"mba|mca|ph\.?d|diploma|cbse\s+xii|cbse\s+x|class\s+xii|class\s+x|"
    r"xii|\bx\b|computer science"
    r")\b",
    re.IGNORECASE,
)

INSTITUTION_PATTERN = re.compile(
    r"\b(?:institute|university|college|school|academy|nitc|national institute of technology|iit|nit)\b",
    re.IGNORECASE,
)

GRADE_PATTERN = re.compile(
    r"\b(?:cgpa|gpa|grade|percentage|percent|marks?)\b\s*:?.*?\d+(?:\.\d+)?\s*(?:/\s*(?:10|100)|%)?"
    r"|\b\d+(?:\.\d+)?\s*/\s*(?:10|100)\b"
    r"|\b\d+(?:\.\d+)?%",
    re.IGNORECASE,
)

EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"\+?\d[\d\s-]{7,}")
LINK_PATTERN = re.compile(r"\b(?:github|linkedin|https?://|www\.)\b", re.IGNORECASE)
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
    text = str(text or "")
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
        "\ufeff": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[ \f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_text(text: str):
    return normalize_text(text)


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


def extract_candidate_name(text: str) -> str:
    for line in get_clean_lines(text):
        if _looks_like_candidate_name(line):
            return line
    return ""


def extract_candidate_email(text: str) -> str:
    match = EMAIL_PATTERN.search(text or "")
    return match.group(0) if match else ""


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
                output_path = _write_resume_face_or_photo(
                    image_bytes,
                    output_directory,
                    page_index,
                    image_index,
                    extension,
                )
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


def _write_resume_face_or_photo(image_bytes, output_directory: Path, page_index: int, image_index: int, extension: str):
    try:
        import cv2
        import numpy as np

        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        if image is not None:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            classifier_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            detector = cv2.CascadeClassifier(classifier_path)
            faces = detector.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(35, 35),
            )

            if len(faces) > 0:
                x, y, width, height = max(faces, key=lambda face: face[2] * face[3])
                padding = int(max(width, height) * 0.25)
                x1 = max(0, x - padding)
                y1 = max(0, y - padding)
                x2 = min(image.shape[1], x + width + padding)
                y2 = min(image.shape[0], y + height + padding)
                crop = image[y1:y2, x1:x2]
                output_path = output_directory / f"resume_face_page_{page_index + 1}_{image_index + 1}.jpg"
                cv2.imwrite(str(output_path), crop)
                return output_path
    except Exception:
        pass

    output_path = output_directory / f"resume_photo_page_{page_index + 1}_{image_index + 1}.{extension}"
    output_path.write_bytes(image_bytes)
    return output_path


def is_section_header(line):
    normalized = _normalize_header(line)
    return normalized in SECTION_HEADERS


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

    parsed = {
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

    print(
        "[resume_parser] parsed counts:",
        f"education={len(parsed['education']['items'])}",
        f"skills={len(parsed['skills']['items'])}",
        f"experience={len(parsed['experience']['items'])}",
        f"projects={len(parsed['projects']['items'])}",
    )

    return parsed


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


def parse_education(education_text: str):
    lines = [line for line in get_clean_lines(education_text) if not _is_noise_line(line)]
    items = []

    for index, line in enumerate(lines):
        if not _is_degree_line(line):
            continue

        if _has_school_board_degree(line):
            items.extend(_parse_school_degree_line(line, lines, index))
            continue

        degree = _clean_degree(_extract_degree_from_line(line))
        institution = _nearest_institution(lines, index)
        duration = _nearest_duration(lines, index)
        description = _extract_grade(line) or _nearest_grade(lines, index)

        items.append({
            "title": degree,
            "institution": institution,
            "degree": degree,
            "duration": duration,
            "description": description,
            "raw_text": clean_text("\n".join(value for value in [institution, duration, degree, description] if value)),
        })

    return _dedupe_education_items(items)


def parse_experience(experience_text: str):
    lines = [line for line in get_clean_lines(experience_text) if not _is_noise_line(line)]
    entries = []
    index = 0

    while index < len(lines):
        line = lines[index]

        if _is_location_line(line):
            index += 1
            continue

        company = ""
        title = ""
        duration = _extract_duration_text(line)
        body = []

        if duration:
            company = clean_text(line.replace(duration, ""))
            index += 1
        elif index + 1 < len(lines) and _extract_duration_text(lines[index + 1]):
            company = line
            duration = _extract_duration_text(lines[index + 1])
            index += 2
        else:
            # Fallback for resumes that put only role/company headings without dates.
            if _looks_like_experience_heading(line):
                title = line
                index += 1
            else:
                index += 1
                continue

        if index < len(lines) and _looks_like_role_title(lines[index]):
            title = lines[index]
            index += 1

        if index < len(lines) and _is_location_line(lines[index]):
            index += 1

        while index < len(lines):
            current = lines[index]
            next_line = lines[index + 1] if index + 1 < len(lines) else ""

            if body and (_extract_duration_text(current) or _extract_duration_text(next_line)) and _looks_like_entry_start(current):
                break

            if is_section_header(current):
                break

            body.append(current)
            index += 1

        heading = clean_text(" | ".join(value for value in [company, title] if value))
        raw_text = clean_text("\n".join([heading, duration, *body]))

        if not title and company:
            title, company = _split_title_company(company)

        entries.append({
            "title": title or company,
            "company": company if title else "",
            "duration": duration,
            "duration_months": _duration_months(duration or raw_text),
            "description": clean_text("\n".join(body)),
            "bullets": [_strip_bullet(item) for item in body if item],
            "technologies": _detect_technologies(raw_text),
            "raw_text": raw_text,
        })

    return [entry for entry in entries if entry.get("title") or entry.get("description") or entry.get("duration")]


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

    skills = []
    seen = set()

    for line in get_clean_lines(skills_text):
        if _normalize_header(line) in SECTION_HEADERS:
            continue

        line = re.sub(r"^[A-Za-z &/]+:\s*", "", line).strip()
        parts = re.split(r"[,|;•\n]+", line)

        for part in parts:
            skill = part.strip(" -:")
            if not skill:
                continue
            if _normalize_header(skill) in SECTION_HEADERS:
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
        if _normalize_header(line) in {"activities", "achievements", "achievements and leadership"}:
            break
        certifications.append(line)
    return certifications


def _finish_project(project):
    body_lines = [_strip_bullet(line) for line in project.get("body", []) if line]
    raw_text = clean_text("\n".join([project.get("title", ""), *body_lines]))
    links = [line for line in body_lines if LINK_PATTERN.search(line)]
    bullets = [line for line in body_lines if not LINK_PATTERN.search(line)]

    return {
        "title": project.get("title", ""),
        "description": clean_text("\n".join(bullets)),
        "bullets": bullets,
        "technologies": _detect_technologies(raw_text),
        "links": links,
        "raw_text": raw_text,
    }


def _normalize_header(line):
    raw = _strip_bullet(str(line or "")).rstrip(":").lower()
    raw = raw.replace("&", " and ")
    raw = re.sub(r"[^a-z ]", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()

    if raw in SECTION_HEADERS:
        return raw

    # Fix PyMuPDF spaced uppercase headings:
    # E DUCATION -> education, T ECHNICAL S KILLS -> technical skills.
    tokens = raw.split()
    rebuilt_tokens = []
    index = 0
    while index < len(tokens):
        if len(tokens[index]) == 1 and index + 1 < len(tokens):
            rebuilt_tokens.append(tokens[index] + tokens[index + 1])
            index += 2
        else:
            rebuilt_tokens.append(tokens[index])
            index += 1

    rebuilt = " ".join(rebuilt_tokens)
    if rebuilt in SECTION_HEADERS:
        return rebuilt

    compact = raw.replace(" ", "")
    if compact in COMPACT_SECTION_HEADERS:
        return COMPACT_CANONICAL_HEADERS.get(compact, raw)

    rebuilt_compact = rebuilt.replace(" ", "")
    if rebuilt_compact in COMPACT_SECTION_HEADERS:
        return COMPACT_CANONICAL_HEADERS.get(rebuilt_compact, rebuilt)

    return raw


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
    if len(line.split()) <= 4 and not _looks_like_project_title(line):
        return True
    return bool(re.match(r"^(and|or|with|using|metadata|generation|analysis|systems|pipeline|strategy|manual)\b", line.lower()))


def _is_noise_line(line):
    normalized = _normalize_header(line)
    stripped = line.strip()
    return bool(
        normalized in {"powered by", "find me online", "sp"}
        or "enhancv.com" in stripped.lower()
        or EMAIL_PATTERN.search(stripped)
        or (not _is_duration_line(stripped) and PHONE_PATTERN.search(stripped))
        or stripped == "\u200b"
    )


def _is_duration_line(line):
    return bool(_extract_duration_text(line) or ANY_DATE_PATTERN.search(line or ""))


def _extract_duration_text(text):
    if not text:
        return ""
    normalized = normalize_text(str(text))
    match = DATE_RANGE_PATTERN.search(normalized)
    if match:
        return re.sub(r"\s+", " ", match.group(0)).strip()
    return ""


def _duration_months(duration_text):
    duration_text = _extract_duration_text(duration_text)
    if not duration_text:
        return 0

    month_map = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    try:
        month_regex = f"({MONTH_PATTERN})"
        match = re.search(
            rf"{month_regex}\s+(\d{{4}})\s*(?:-|to)\s*(present|{month_regex}\s+\d{{4}})",
            duration_text,
            re.IGNORECASE,
        )
        if match:
            start_month = month_map[match.group(1).lower()]
            start_year = int(match.group(2))
            end_part = match.group(3)

            if end_part.lower() == "present":
                end_year = datetime.now().year
                end_month = datetime.now().month
            else:
                end_match = re.search(rf"{month_regex}\s+(\d{{4}})", end_part, re.IGNORECASE)
                end_month = month_map[end_match.group(1).lower()]
                end_year = int(end_match.group(2))

            return max(((end_year - start_year) * 12) + (end_month - start_month) + 1, 0)

        year_match = re.search(r"(\d{4})\s*(?:-|to)\s*(present|\d{4})", duration_text, re.IGNORECASE)
        if year_match:
            start_year = int(year_match.group(1))
            end_year = datetime.now().year if year_match.group(2).lower() == "present" else int(year_match.group(2))
            return max((end_year - start_year + 1) * 12, 0)
    except Exception:
        return 0

    return 0


def _is_degree_line(line):
    return bool(DEGREE_PATTERN.search(line or ""))


def _is_institution_line(line):
    return bool(INSTITUTION_PATTERN.search(line or ""))


def _is_bullet_line(line):
    return bool(BULLET_PATTERN.match(line.strip()))


def _is_location_line(line):
    return bool(re.fullmatch(r"[A-Za-z .'-]+,\s*[A-Za-z .'-]+", line.strip()))


def _has_school_board_degree(line):
    return bool(re.search(r"\b(?:CBSE\s+XII|Class\s+XII|XII|CBSE\s+X|Class\s+X|\bX\b)\b", line, re.IGNORECASE))


def _parse_school_degree_line(line, lines, index):
    items = []
    institution = _nearest_school(lines, index) or _nearest_institution(lines, index)
    duration = _nearest_duration(lines, index) or _find_graduation_line(lines, index)

    board_matches = re.finditer(
        r"(?P<degree>CBSE\s+XII(?:\s+[A-Za-z]+)?|Class\s+XII(?:\s+[A-Za-z]+)?|XII(?:\s+[A-Za-z]+)?|CBSE\s+X|Class\s+X|\bX\b)"
        r"\s*:??\s*(?P<grade>\d+(?:\.\d+)?%)?",
        line,
        re.IGNORECASE,
    )

    for match in board_matches:
        degree = _clean_degree(match.group("degree"))
        grade = match.group("grade") or _extract_grade(line)
        items.append({
            "title": degree,
            "institution": institution,
            "degree": degree,
            "duration": duration,
            "description": grade,
            "raw_text": clean_text("\n".join(value for value in [institution, duration, degree, grade] if value)),
        })

    return items


def _extract_degree_from_line(line):
    line = line.strip(" -:")
    split_line = re.split(r";|\bCGPA\b|\bGPA\b|\b\d+(?:\.\d+)?%", line, maxsplit=1, flags=re.IGNORECASE)[0]
    match = DEGREE_PATTERN.search(split_line)
    if match:
        # For B.Tech Mechanical Engineering, keep the branch after the degree.
        return split_line.strip(" -:")
    return split_line.strip(" -:")


def _clean_degree(text):
    text = re.sub(r":.*$", "", text or "").strip()
    text = text.replace("(", " ").replace(")", " ")
    text = text.strip(" -:;")
    text = re.sub(r"\s+", " ", text)

    replacements = {
        "xii": "XII",
        "x": "X",
        "cbse": "CBSE",
        "class": "Class",
        "b.tech": "B.Tech",
        "b.e": "B.E",
        "m.tech": "M.Tech",
        "b.sc": "B.Sc",
        "m.sc": "M.Sc",
        "mba": "MBA",
        "mca": "MCA",
    }

    words = []
    for word in text.split():
        key = word.lower().strip(".")
        if key in replacements:
            words.append(replacements[key])
        else:
            words.append(word)

    return " ".join(words)


def _extract_grade(line):
    if not line:
        return ""

    cgpa_match = re.search(r"\bCGPA\s*:??\s*\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?", line, re.IGNORECASE)
    if cgpa_match:
        return re.sub(r"\s+", " ", cgpa_match.group(0)).replace("CGPA ", "CGPA: ")

    percentage_match = re.search(r"\b\d+(?:\.\d+)?%", line)
    if percentage_match:
        return percentage_match.group(0)

    score_match = re.search(r"\b\d+(?:\.\d+)?\s*/\s*(?:10|100)\b", line)
    if score_match:
        return score_match.group(0)

    return ""


def _nearest_institution(lines, index):
    candidates = []
    for cursor in range(index - 1, max(-1, index - 4), -1):
        if cursor < 0:
            break
        line = lines[cursor]
        if _is_degree_line(line):
            break
        if _is_institution_line(line) or _is_location_line(line):
            candidates.insert(0, line)
    return clean_text(" ".join(candidates))


def _nearest_school(lines, index):
    for cursor in range(index - 1, max(-1, index - 5), -1):
        line = lines[cursor]
        if re.search(r"\bschool\b", line, re.IGNORECASE):
            return line
    return ""


def _nearest_duration(lines, index):
    for cursor in range(index, min(len(lines), index + 4)):
        duration = _extract_duration_text(lines[cursor])
        if duration:
            return duration
        if re.search(r"\bgraduated\s+\d{4}\b", lines[cursor], re.IGNORECASE):
            return lines[cursor]
    return ""


def _nearest_grade(lines, index):
    for cursor in range(index, min(len(lines), index + 3)):
        grade = _extract_grade(lines[cursor])
        if grade:
            return grade
    return ""


def _find_graduation_line(lines, index):
    for cursor in range(index, min(len(lines), index + 4)):
        if re.search(r"\bgraduated\s+\d{4}\b", lines[cursor], re.IGNORECASE):
            return lines[cursor]
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


def _looks_like_experience_heading(line):
    lowered = line.lower()
    if is_section_header(line) or _is_bullet_line(line):
        return False
    if line.strip().endswith((".", ";")):
        return False
    if len(line.split()) > 14:
        return False

    role_words = {
        "intern", "developer", "engineer", "analyst", "lead", "member", "associate",
        "software", "research", "assistant", "trainee",
    }
    company_words = {"novac", "google", "gdsc", "nit", "nitc", "labs", "technologies", "systems"}

    return _has_word_keyword(lowered, role_words) or _has_word_keyword(lowered, company_words)


def _looks_like_role_title(line):
    lowered = line.lower()
    if _is_location_line(line) or _is_duration_line(line) or line.strip().endswith("."):
        return False
    role_words = {
        "intern", "developer", "engineer", "analyst", "lead", "member", "associate",
        "software", "research", "assistant", "trainee",
    }
    return _has_word_keyword(lowered, role_words) or len(line.split()) <= 5


def _looks_like_entry_start(line):
    if _is_location_line(line):
        return False
    return bool(_extract_duration_text(line) or _looks_like_experience_heading(line))


def _split_title_company(heading):
    heading = clean_text(heading)

    if " | " in heading:
        left, right = heading.split(" | ", 1)
        if _extract_duration_text(left) or _looks_like_company_name(left):
            return right.strip(), left.strip()
        return left.strip(), right.strip()

    for separator in [",", " - "]:
        if separator in heading and not _extract_duration_text(heading):
            title, company = heading.split(separator, 1)
            return title.strip(), company.strip()

    return heading.strip(), ""


def _looks_like_company_name(line):
    if not line:
        return False
    if _is_location_line(line):
        return False
    company_words = {"novac", "nit", "nitc", "google", "gdsc", "company", "labs", "club", "technologies"}
    return line.isupper() or _has_word_keyword(line.lower(), company_words)


def _looks_like_project_title(line):
    if is_section_header(line) or _is_duration_line(line) or _is_bullet_line(line):
        return False
    if len(line.split()) > 14:
        return False
    if line.strip().endswith((".", ";")):
        return False
    if re.match(r"^(and|or|with|using|generation|analysis|built|implemented|calculated|tuned|hand|manual|labeled|strategy|systems)\b", line.lower()):
        return False

    has_parenthesized_tech = bool(
        re.search(
            r"\([^)]*(python|react|c\+\+|java|sql|fastapi|numpy|pandas|pytorch|tensorflow|opencv|flask)[^)]*\)",
            line,
            re.IGNORECASE,
        )
    )
    has_separator_tech = bool(
        re.search(
            r"\|.*\b(python|react|c\+\+|java|sql|fastapi|numpy|pandas|pytorch|tensorflow|opencv|flask|nlp|matplotlib)\b",
            line,
            re.IGNORECASE,
        )
    )
    title_case_words = sum(1 for word in line.split() if word[:1].isupper() or any(char.isdigit() for char in word))
    return has_parenthesized_tech or has_separator_tech or title_case_words >= max(1, len(line.split()) - 1)


def _clean_project_title(line):
    return re.sub(r"\s*github\s*$", "", line, flags=re.IGNORECASE).strip(" -")


def _detect_technologies(text):
    technologies = []
    for technology in TECHNOLOGY_KEYWORDS:
        pattern = re.escape(technology)
        if re.search(rf"(?<!\w){pattern}(?!\w)", text or "", re.IGNORECASE):
            normalized = "HuggingFace" if technology == "Hugging Face" else technology
            if normalized not in technologies:
                technologies.append(normalized)
    return technologies


def _has_word_keyword(text, keywords):
    lowered = (text or "").lower()
    for keyword in keywords:
        pattern = r"(?<![a-z])" + re.escape(keyword.lower()) + r"(?![a-z])"
        if re.search(pattern, lowered):
            return True
    return False


def _strip_bullet(line):
    return BULLET_PATTERN.sub("", line.strip()).strip()


def _looks_like_candidate_name(line):
    if not line or len(line.split()) > 5:
        return False
    if any(char.isdigit() for char in line):
        return False
    if EMAIL_PATTERN.search(line) or LINK_PATTERN.search(line):
        return False
    if line.strip().startswith(":"):
        return False

    blocked = {
        "education", "skills", "projects", "experience", "certifications", "resume",
        "find me online", "course", "email", "mobile", "github", "linkedin", "cgpa",
    }
    if _normalize_header(line) in blocked:
        return False

    return bool(re.search(r"[A-Za-z]{2,}", line))
