from keyword_match import calculate_skill_match
from education_match import calculate_education_match
from experience_match import calculate_experience_match
from project_quality import calculate_project_quality
from ats_calculator import calculate_final_ats


def calculate_ats(
    resume,
    jd
):

    skill_result = calculate_skill_match(
        resume["data"]["skills"],
        jd["required_skills"]
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

    final_score = calculate_final_ats(
        skill_result["score"],
        education_result["score"],
        experience_result["score"],
        project_result["score"]
    )
    SHORTLIST_THRESHOLD = 75

    shortlisted = (final_score >= SHORTLIST_THRESHOLD)
    
    if shortlisted:
        interview_link = ("https://meet.google.com/interview-room")

    else:
        interview_link = None
    
    return {

    "candidate_name":
        resume["data"]["candidate_name"],

    "final_score":
        final_score,

    "shortlisted":
        shortlisted,

    "interview_link":
        interview_link,

    "matched_skills":
        skill_result["matched_skills"],

    "missing_skills":
        skill_result["missing_skills"]
}
