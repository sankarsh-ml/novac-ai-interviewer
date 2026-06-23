def calculate_project_quality(
    projects,
    required_skills,
    keywords,
    job_title=""
):

    if not projects:
        return {
            "score": 0,
            "reason": "No projects found"
        }

    # -------------------------
    # Quantity Score
    # -------------------------

    project_count = len(projects)

    if project_count >= 5:
        quantity_score = 100

    elif project_count >= 3:
        quantity_score = 80

    else:
        quantity_score = 60

    # -------------------------
    # Build Project Corpus
    # -------------------------

    project_text = ""

    for project in projects:

        project_text += " "

        project_text += project.get(
            "title",
            ""
        )

        project_text += " "

        project_text += project.get(
            "description",
            ""
        )

        project_text += " "

        project_text += " ".join(
            project.get(
                "technologies",
                []
            )
        )

    project_text = project_text.lower()

    # -------------------------
    # Matching Targets
    # -------------------------

    targets = []

    targets.extend(required_skills)
    targets.extend(keywords)

    if job_title:
        targets.append(job_title)

    matched = set()

    for target in targets:

        target = target.lower().strip()

        if not target:
            continue

        if target in project_text:

            matched.add(target)

    # -------------------------
    # Relevance Score
    # -------------------------

    relevance_score = (
        len(matched)
        /
        max(len(targets), 1)
    ) * 100

    # -------------------------
    # Final Project Score
    # -------------------------

    final_score = (
        0.30 * quantity_score
        +
        0.70 * relevance_score
    )

    return {

        "score": round(
            final_score,
            2
        ),

        "project_count": project_count,

        "matched": list(
            matched
        ),

        "quantity_score": quantity_score,

        "relevance_score": round(
            relevance_score,
            2
        )
    }