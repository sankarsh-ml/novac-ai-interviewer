def calculate_project_quality(
    projects,
    required_skills=None,
    keywords=None,
    job_title=""
):
    required_skills = required_skills or []
    keywords = keywords or []

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
    # Relevance Matching
    # ------------------------

    targets = []
    targets.extend(required_skills)
    targets.extend(keywords)

    if job_title:
        targets.append(job_title)

    matched = set()

    for project in projects:

        project_text = (
            project.get("title", "")
            + " "
            + project.get("description", "")
            + " "
            + " ".join(project.get("technologies", []))
        ).lower()

        for target in targets:
            target = str(target or "").lower().strip()

            if target and target in project_text:

                matched.add(target)

    # ------------------------
    # Quality Score
    # ------------------------

    if len(targets) == 0:

        quality_score = 0

    else:

        quality_score = (
            len(matched)
            /
            len(targets)
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
        "matched_keywords": len(matched),
        "matched": list(matched),
        "quantity_score": quantity_score,
        "quality_score": round(
            quality_score,
            2
        )
    }
