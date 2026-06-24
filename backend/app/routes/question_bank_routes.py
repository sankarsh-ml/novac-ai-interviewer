from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form
)
import re
from pydantic import BaseModel

from app.services.question_bank_service import (
    save_question_bank,
    load_question_bank
)

router = APIRouter()


class QuestionItem(BaseModel):
    question: str
    expected_answer: str


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


@router.post(
    "/question-bank/upload"
)
async def upload_question_file(
    job_id: str = Form(...),
    file: UploadFile = File(...)
):

    content = (
        await file.read()
    ).decode("utf-8")

    questions = []

    lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip()
    ]

    i = 0

    while i < len(lines):

        if (
            i + 1 < len(lines)
            and "ANS" in lines[i + 1].upper()
        ):

            question = re.sub(
                r"^\d+\)\s*",
                "",
                lines[i]
            ).strip()

            answer = (
                lines[i + 1]
                .replace("ANS:=", "")
                .replace("ANS:", "")
                .strip()
            )

            questions.append({
                "question": question,
                "expected_answer": answer
            })

            i += 2

        else:
            i += 1

    print("QUESTIONS FOUND:")
    print(questions)

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