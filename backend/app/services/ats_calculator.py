def calculate_final_ats(
    skill_score,
    education_score,
    experience_score,
    project_score
):

    final_score = (
        0.45 * skill_score +
        0.15 * education_score +
        0.10 * experience_score +
        0.30 * project_score
    )

    return round(
        final_score,
        2
    )