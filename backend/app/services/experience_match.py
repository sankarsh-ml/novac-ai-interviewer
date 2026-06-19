def calculate_experience_match(
    resume_data,
    required_experience
):

    if "experience" not in resume_data:

        return {
            "score": 0,
            "years": 0
        }

    experiences = resume_data["experience"]

    total_months = 0

    for exp in experiences:

        total_months += exp.get(
            "duration_months",
            0
        )

    total_years = total_months / 12

    if required_experience == 0:

        score = 100

    elif total_years >= required_experience:

        score = 100

    else:

        score = (
            total_years /
            required_experience
        ) * 100

    return {
        "score": round(score, 2),
        "years": round(total_years, 1)
    }