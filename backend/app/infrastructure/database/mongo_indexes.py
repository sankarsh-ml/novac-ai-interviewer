from __future__ import annotations


def ensure_indexes(db) -> None:
    db.jobs.create_index("jobId")
    db.jobs.create_index("id")
    db.candidates.create_index("jobId")
    db.candidates.create_index("job_id")
    db.candidates.create_index("candidateId")
    db.candidates.create_index("application_id", unique=True)
    db.candidates.create_index("email")
    db.question_bank.create_index("jobId")
    db.question_bank.create_index("job_id")
    question_indexes = db.question_bank.index_information()
    question_id_index = question_indexes.get("questionId_1")

    if question_id_index and question_id_index.get("unique"):
        db.question_bank.drop_index("questionId_1")

    db.question_bank.create_index("questionId")
    db.question_bank.create_index("question_id")
    db.interviews.create_index("interviewId")
    db.interviews.create_index("candidateId")
    db.interviews.create_index("application_id")
    db.interviews.create_index("jobId")
    db.interviews.create_index("interviewLinkToken")
    db.interviews.create_index("token", unique=True, sparse=True)
    db.interview_answers.create_index("interviewId")
    db.interview_answers.create_index("candidateId")
    db.interview_answers.create_index("application_id")
    db.identity_verifications.create_index("candidateId")
    db.identity_verifications.create_index("application_id")
    db.face_verifications.create_index("candidateId")
    db.face_verifications.create_index("application_id")
    db.reports.create_index("candidateId")
    db.reports.create_index("jobId")
    db.admin_users.create_index("username", unique=True)
    db.admin_users.create_index("adminId")
