from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form
)
from pydantic import BaseModel, Field

from app.application.services.question_bank_service import (
    filter_question_bank_questions,
    get_question_bank_filters,
    load_question_bank,
    normalize_question_bank_questions,
    parse_question_bank_text,
    save_question_bank,
)

router = APIRouter()


class QuestionItem(BaseModel):
    question: str
    expected_answer: str = "N/A"
    difficulty: str = "medium"
    area_of_interest: str = "General"
    category: str = "General"
    tags: list[str] = Field(default_factory=list)
    job_role: str = ""
    score_weight: float = 1
    source: str = "manual"


class QuestionBankRequest(BaseModel):
    job_id: str
    questions: list[QuestionItem]


class QuestionUpdateRequest(QuestionItem):
    job_id: str


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


@router.get("/jobs/{job_id}/question-bank")
def get_job_question_bank(job_id: str):
    return get_question_bank(job_id)


@router.get("/question-bank/questions")
def get_question_bank_questions(
    job_id: str,
    difficulty: str = "all",
    area_of_interest: str = "all",
    search: str = "",
    tags: str = "",
    job_role: str = "all",
):
    questions = load_question_bank(job_id)
    tag_filters = [tag.strip() for tag in tags.split(",") if tag.strip()]
    filtered = filter_question_bank_questions(
        questions,
        difficulty=difficulty,
        area_of_interest=area_of_interest,
        search=search,
        tags=tag_filters,
        job_role=job_role,
    )

    return {
        "success": True,
        "questions": filtered,
        "count": len(filtered),
    }


@router.get("/question-bank/filters")
def get_filters(job_id: str):
    return {
        "success": True,
        "filters": get_question_bank_filters(job_id),
    }


@router.post("/question-bank/questions")
def save_question_bank_questions(payload: QuestionBankRequest):
    questions = normalize_question_bank_questions(
        [
            q.model_dump()
            for q in payload.questions
        ],
        job_id=payload.job_id,
    )

    save_question_bank(payload.job_id, questions)

    return {
        "success": True,
        "questions_saved": len(questions),
        "questions": questions,
    }


@router.put("/question-bank/questions/{question_id}")
def update_question(question_id: str, payload: QuestionUpdateRequest):
    questions = load_question_bank(payload.job_id)
    updated_questions = []
    found = False

    for question in questions:
        current_id = str(question.get("_id") or question.get("id") or question.get("question_id") or "")

        if current_id == question_id:
            updated = {
                **question,
                **payload.model_dump(exclude={"job_id"}),
                "_id": question_id,
                "id": question_id,
                "question_id": question_id,
            }
            updated_questions.append(updated)
            found = True
        else:
            updated_questions.append(question)

    if not found:
        return {
            "success": False,
            "message": "Question not found",
        }

    save_question_bank(payload.job_id, updated_questions)

    return {
        "success": True,
        "question_id": question_id,
        "questions": load_question_bank(payload.job_id),
    }


@router.delete("/question-bank/questions/{question_id}")
def delete_question(question_id: str, job_id: str):
    questions = load_question_bank(job_id)
    updated_questions = [
        question
        for question in questions
        if str(question.get("_id") or question.get("id") or question.get("question_id") or "") != question_id
    ]

    if len(updated_questions) == len(questions):
        return {
            "success": False,
            "message": "Question not found",
        }

    save_question_bank(job_id, updated_questions)

    return {
        "success": True,
        "questions_deleted": 1,
        "questions": updated_questions,
    }


@router.delete("/question-bank")
def clear_question_bank(job_id: str):
    save_question_bank(job_id, [])

    return {
        "success": True,
        "message": "Question bank cleared",
        "questions": [],
    }


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
        ),
        "questions": questions
    }


@router.post("/question-bank/parse-upload")
async def parse_question_file(file: UploadFile = File(...)):
    content = (await file.read()).decode("utf-8", errors="replace")
    questions = parse_question_bank_text(content)

    return {
        "success": True,
        "questions": questions,
        "questions_found": len(questions),
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
