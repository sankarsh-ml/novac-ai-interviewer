def calculate_education_match(candidate_education,required_education):

    for edu in candidate_education:

        if required_education.lower() in \
           edu["degree"].lower():

            return {
                "score": 100,
                "matched": True,
                "degree": edu["degree"]
            }

    return {
        "score": 0,
        "matched": False,
        "degree": None
    }

