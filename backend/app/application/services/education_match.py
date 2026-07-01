import re


def calculate_education_match(candidate_education, required_education):
    """
    Robust education matcher for ATS scoring.

    Handles cases like:
    - Required: B.Tech / B.E / Bachelor's degree
    - Candidate: B.Tech Mechanical Engineering
    - Candidate: CBSE XII / CBSE X should not be treated as highest degree
    """

    if not candidate_education:
        return {
            "score": 0,
            "matched": False,
            "degree": None,
            "reason": "No education data found"
        }

    required_text = _normalize(required_education or "")

    if not required_text:
        return {
            "score": 100,
            "matched": True,
            "degree": _best_candidate_degree(candidate_education),
            "reason": "No specific education requirement"
        }

    best_score = 0
    best_degree = None
    best_reason = "No matching education requirement found"

    for edu in candidate_education:
        degree = (
            edu.get("degree")
            or edu.get("title")
            or edu.get("raw_text")
            or ""
        )

        raw_text = " ".join(
            str(edu.get(field, ""))
            for field in ["degree", "title", "institution", "description", "raw_text"]
        )

        candidate_text = _normalize(raw_text)
        candidate_degree = _normalize(degree)

        score, reason = _score_single_education(candidate_text, candidate_degree, required_text)

        if score > best_score:
            best_score = score
            best_degree = degree
            best_reason = reason

    return {
        "score": round(best_score, 2),
        "matched": best_score >= 60,
        "degree": best_degree,
        "reason": best_reason
    }


def _score_single_education(candidate_text, candidate_degree, required_text):
    candidate_level = _detect_level(candidate_text)
    required_level = _detect_level(required_text)

    candidate_branch = _detect_branch(candidate_text)
    required_branch = _detect_branch(required_text)

    # Exact or near-exact text match
    if required_text in candidate_text or candidate_degree in required_text:
        return 100, "Exact education text match"

    # Required bachelor's / B.Tech / B.E and candidate has B.Tech / B.E
    if required_level == "bachelors" and candidate_level == "bachelors":
        if required_branch and candidate_branch:
            if required_branch == candidate_branch:
                return 100, "Matching bachelor's degree and specialization"

            if _branches_are_related(required_branch, candidate_branch):
                return 85, "Related engineering bachelor's degree"

            # Example: CS required, Mechanical candidate.
            # Still acceptable for software/AI roles if candidate has strong skills.
            return 75, "Bachelor's degree matched, specialization differs"

        return 100, "Bachelor's degree requirement matched"

    # Required engineering degree and candidate has any engineering bachelor's
    if _requires_engineering(required_text) and _has_engineering_degree(candidate_text):
        return 90, "Engineering degree requirement matched"

    # Required postgraduate and candidate has postgraduate
    if required_level == "masters" and candidate_level == "masters":
        return 100, "Master's degree requirement matched"

    # Required masters but candidate only has bachelors
    if required_level == "masters" and candidate_level == "bachelors":
        return 60, "Bachelor's found but master's preferred/required"

    # Required diploma/12th and candidate has higher degree
    if required_level in {"school", "diploma"} and candidate_level in {"bachelors", "masters"}:
        return 100, "Candidate has higher qualification than required"

    # Candidate has school education only
    if candidate_level == "school":
        return 20, "Only school-level education matched"

    return 0, "Education does not match requirement"


def _normalize(text):
    text = str(text or "").lower()

    replacements = {
        "b.tech": "btech",
        "b tech": "btech",
        "b.e": "be",
        "b e": "be",
        "m.tech": "mtech",
        "m tech": "mtech",
        "b.sc": "bsc",
        "b sc": "bsc",
        "m.sc": "msc",
        "m sc": "msc",
        "computer science": "cs",
        "cse": "cs",
        "information technology": "it",
        "artificial intelligence": "ai",
        "machine learning": "ml",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[^a-z0-9+/ ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _detect_level(text):
    if not text:
        return None

    masters_keywords = [
        "mtech", "m tech", "masters", "master", "msc", "mba", "mca", "postgraduate"
    ]

    bachelors_keywords = [
        "btech", "be", "bachelor", "bachelors", "bsc", "bca", "undergraduate",
        "engineering"
    ]

    diploma_keywords = [
        "diploma", "polytechnic"
    ]

    school_keywords = [
        "cbse xii", "class xii", "xii", "12th",
        "cbse x", "class x", "10th"
    ]

    if any(keyword in text for keyword in masters_keywords):
        return "masters"

    if any(keyword in text for keyword in bachelors_keywords):
        return "bachelors"

    if any(keyword in text for keyword in diploma_keywords):
        return "diploma"

    if any(keyword in text for keyword in school_keywords):
        return "school"

    return None


def _detect_branch(text):
    branch_patterns = {
        "cs": [
            "cs", "computer science", "software", "computer engineering"
        ],
        "it": [
            "it", "information technology"
        ],
        "ai": [
            "ai", "ml", "data science", "artificial intelligence", "machine learning"
        ],
        "ece": [
            "ece", "electronics", "communication"
        ],
        "eee": [
            "eee", "electrical"
        ],
        "mechanical": [
            "mechanical", "mech"
        ],
        "civil": [
            "civil"
        ],
    }

    for branch, keywords in branch_patterns.items():
        if any(keyword in text for keyword in keywords):
            return branch

    return None


def _branches_are_related(required_branch, candidate_branch):
    related_groups = [
        {"cs", "it", "ai"},
        {"ece", "eee"},
    ]

    for group in related_groups:
        if required_branch in group and candidate_branch in group:
            return True

    return False


def _requires_engineering(text):
    return any(
        keyword in text
        for keyword in [
            "engineering",
            "btech",
            "be",
            "bachelor of engineering",
            "bachelor of technology"
        ]
    )


def _has_engineering_degree(text):
    return any(
        keyword in text
        for keyword in [
            "engineering",
            "btech",
            "be",
            "mechanical",
            "computer science",
            "cs",
            "it",
            "electronics",
            "electrical",
            "civil"
        ]
    )


def _best_candidate_degree(candidate_education):
    for edu in candidate_education:
        degree = edu.get("degree") or edu.get("title")
        if degree:
            return degree

    return None