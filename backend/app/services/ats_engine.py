from app.services.keyword_match import calculate_skill_match
from app.services.education_match import calculate_education_match
from app.services.experience_match import calculate_experience_match
from app.services.project_quality import calculate_project_quality
from app.services.semantic_match import get_semantic_score


def calculate_ats(
    resume,
    jd
):

    skill_result = calculate_skill_match(
        resume["data"].get("raw_text", ""),
        jd["required_skills"],
        resume["data"].get("skills", []),
    )

    education_result = calculate_education_match(
        resume["data"]["education"],
        jd["education"]
    )

    experience_result = calculate_experience_match(
        resume["data"],
        jd["experience"]
    )

    all_projects = list(resume["data"].get("projects",[]))

    for exp in resume["data"].get("experience",[]):
        description = exp.get("description","")
        if len(description) > 100:

            all_projects.append({
                "title":
                    exp.get(
                        "title",
                        ""
                    ),

                "description":
                    description,

                "technologies":
                    exp.get(
                        "technologies",
                        []
                    )
            })

    project_result = calculate_project_quality(
        all_projects,
        jd["required_skills"],
        jd["keywords"],
        jd["title"]
    )

    semantic_corpus = ""

    semantic_corpus += " ".join(
        resume["data"].get(
            "skills",
            []
        )
    )

    semantic_corpus += " "

    for exp in resume["data"].get(
        "experience",
        []
    ):
        semantic_corpus += (
            exp.get("title", "")
            + " "
            + exp.get("description", "")
            + " "
        )

    for project in resume["data"].get(
        "projects",
        []
    ):
        semantic_corpus += (
            project.get("title", "")
            + " "
            + project.get("description", "")
            + " "
        )

    semantic_score = get_semantic_score(
    semantic_corpus,
    jd["description"])

    print("\n========== ATS DEBUG ==========")

    print("Semantic:", semantic_score)

    print("Skill:", skill_result["score"])

    print("Education:", education_result["score"])

    print("Experience:", experience_result["score"])

    print("Project:", project_result["score"])

    print("===============================\n")
    ats_score = (
        0.35 * semantic_score
        +
        0.30 * skill_result["score"]
        +
        0.15 * education_result["score"]
        +
        0.10 * experience_result["score"]
        +
        0.10 * project_result["score"]
    )

    ats_score = round(ats_score, 2)

    SHORTLIST_THRESHOLD = 70

    shortlisted = ats_score >= SHORTLIST_THRESHOLD

    status = (
        "passed"
        if shortlisted
        else "failed"
    )

    interview_link = (
        "https://meet.google.com/interview-room"
        if shortlisted
        else None
    )

    return {

        "candidate_name":
            resume["data"]["candidate_name"],

        "atsScore":
            ats_score,

        "shortlisted":
            shortlisted,

        "passed":
            shortlisted,

        "status":
            status,

        "ats_status":
            status,

        "interview_link":
            interview_link,

        "matched_skills":
            skill_result["matched_skills"],

        "missing_skills":
            skill_result["missing_skills"],

        "semantic_score":
            semantic_score,

        "skill_score":
            skill_result["score"],

        "education_score":
            education_result["score"],

        "experience_score":
            experience_result["score"],

        "project_score":
            project_result["score"]
    }