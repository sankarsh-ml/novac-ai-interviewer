from app.services.keyword_match import calculate_skill_match
from app.services.education_match import calculate_education_match
from app.services.experience_match import calculate_experience_match
from app.services.project_quality import calculate_project_quality
from app.services.ats_calculator import calculate_final_ats


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

    project_result = calculate_project_quality(
        resume["data"]["projects"],
        jd["keywords"]
    )

    weighted_score = calculate_final_ats(
        skill_result["score"],
        education_result["score"],
        experience_result["score"],
        project_result["score"]
    )
    ats_score = skill_result["score"]
    SHORTLIST_THRESHOLD = 70

    shortlisted = (ats_score >= SHORTLIST_THRESHOLD)
    status = "passed" if shortlisted else "failed"
    
    if shortlisted:
        interview_link = ("https://meet.google.com/interview-room")

    else:
        interview_link = None
    
    return {

    "candidate_name":
        resume["data"]["candidate_name"],

    "ats_score":
        ats_score,

    "atsScore":
        ats_score,

    "final_score":
        ats_score,

    "weighted_score":
        weighted_score,

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
        skill_result["missing_skills"]
}
