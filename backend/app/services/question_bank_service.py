import json
from pathlib import Path


QUESTION_BANK_DIR = Path(
    "app/storage/question_banks"
)

QUESTION_BANK_DIR.mkdir(
    parents=True,
    exist_ok=True
)


def save_question_bank(job_id, questions):

    file_path = (
        QUESTION_BANK_DIR /
        f"{job_id}.json"
    )

    with open(
        file_path,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            {
                "job_id": job_id,
                "questions": questions
            },
            f,
            indent=4
        )


def load_question_bank(job_id):

    file_path = (
        QUESTION_BANK_DIR /
        f"{job_id}.json"
    )

    if not file_path.exists():
        return []

    with open(
        file_path,
        "r",
        encoding="utf-8"
    ) as f:
        data = json.load(f)

    return data.get(
        "questions",
        []
    )