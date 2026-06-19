def calculate_skill_match(resume_skills,required_skills):
    matched = []
    missing = []
    for skill in required_skills:
        if skill.lower() in [ s.lower() for s in resume_skills]:
            matched.append(skill)
        else:
            missing.append(skill)

    score = (len(matched)/len(required_skills)) * 100

    return {
        "score": round(score, 2),
        "matched_skills": matched,
        "missing_skills": missing
    }
