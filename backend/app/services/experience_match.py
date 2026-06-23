import re
from datetime import datetime


def calculate_experience_match(
    resume_data,
    required_experience
):
    experiences = resume_data.get(
        "experience",
        []
    )

    if not experiences:
        return {
            "score": 0,
            "years": 0
        }

    total_months = 0

    for exp in experiences:
        duration = exp.get(
            "duration",
            ""
        )

        total_months += extract_months(
            duration
        )

    total_years = (
        total_months / 12
    )

    # Student-friendly scoring
    if required_experience == 0:

        score = 100

    elif total_years >= required_experience:

        score = 100

    elif total_years > 0:

        score = max(
            50,
            (
                total_years /
                required_experience
            ) * 100
        )

    else:

        score = 20

    return {
        "score": round(score, 2),
        "years": round(total_years, 1)
    }


def extract_months(
    duration_text
):
    if not duration_text:
        return 0

    duration_text = duration_text.strip()

    pattern = (
        r"([A-Za-z]+)\s+(\d{4})"
        r"\s*-\s*"
        r"([A-Za-z]+|Present)"
        r"\s*(\d{4})?"
    )

    match = re.search(
        pattern,
        duration_text,
        re.IGNORECASE
    )

    if not match:
        return 0

    try:

        start_month = datetime.strptime(
            match.group(1)[:3],
            "%b"
        ).month

        start_year = int(
            match.group(2)
        )

        if (
            match.group(3).lower()
            == "present"
        ):

            end_date = datetime.now()

        else:

            end_month = datetime.strptime(
                match.group(3)[:3],
                "%b"
            ).month

            end_year = int(
                match.group(4)
            )

            end_date = datetime(
                end_year,
                end_month,
                1
            )

        start_date = datetime(
            start_year,
            start_month,
            1
        )

        months = (
            (end_date.year - start_date.year)
            * 12
            +
            (
                end_date.month -
                start_date.month
            )
        )

        return max(
            months,
            0
        )

    except Exception:
        return 0