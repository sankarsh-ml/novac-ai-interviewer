def calculate_project_quality(
    projects,
    hr_keywords
):

    # No projects submitted

    if len(projects) == 0:

        return {
            "score": 0,
            "reason": "No projects found"
        }

    # ------------------------
    # Quantity Score
    # ------------------------

    project_count = len(projects)

    if project_count >= 5:
        quantity_score = 100

    elif project_count >= 3:
        quantity_score = 75

    else:
        quantity_score = 50

    # ------------------------
    # Keyword Matching
    # ------------------------

    matched_keywords = 0

    for project in projects:

        project_text = (
            project.get("title", "")
            + " "
            + project.get("description", "")
        ).lower()

        for keyword in hr_keywords:

            if keyword.lower() in project_text:

                matched_keywords += 1

    # ------------------------
    # Quality Score
    # ------------------------

    if len(hr_keywords) == 0:

        quality_score = 0

    else:

        quality_score = (
            matched_keywords
            /
            len(hr_keywords)
        ) * 100

    # Prevent scores > 100

    quality_score = min(
        quality_score,
        100
    )

    # ------------------------
    # Final Project Score
    # ------------------------

    final_score = (
        0.4 * quantity_score +
        0.6 * quality_score
    )

    return {
        "score": round(final_score, 2),
        "project_count": project_count,
        "matched_keywords": matched_keywords,
        "quantity_score": quantity_score,
        "quality_score": round(
            quality_score,
            2
        )
    }