from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form
)
from pydantic import BaseModel

from app.services.question_bank_service import (
    load_question_bank,
    parse_question_bank_text,
    save_question_bank,
)

router = APIRouter()


class QuestionItem(BaseModel):
    question: str
    expected_answer: str = ""
    difficulty: str = "Medium"
    category: str = "Question Bank"


class QuestionBankRequest(BaseModel):
    job_id: str
    questions: list[QuestionItem]


@router.post("/question-bank/save")
def save_questions(
    payload: QuestionBankRequest
):

    save_question_bank(
        payload.job_id,
        [
            q.model_dump()
            for q in payload.questions
        ]
    )

    return {
        "success": True,
        "message": "Question bank saved"
    }


@router.get(
    "/question-bank/{job_id}"
)
def get_question_bank(job_id: str):

    questions = load_question_bank(
        job_id
    )

    return {
        "success": True,
        "questions": questions
    }


@router.get("/jobs/{job_id}/question-bank")
def get_job_question_bank(job_id: str):
    return get_question_bank(job_id)


@router.post(
    "/question-bank/upload"
)
async def upload_question_file(
    job_id: str = Form(...),
    file: UploadFile = File(...)
):

    content = (await file.read()).decode("utf-8", errors="replace")
    questions = parse_question_bank_text(content)

    print(f"[Question bank] job_id={job_id} questions_found={len(questions)}")

    save_question_bank(
        job_id,
        questions
    )

    return {
        "success": True,
        "questions_saved": len(
            questions
        )
    }
