from sentence_transformers import SentenceTransformer
from sentence_transformers import util

try:
    model = SentenceTransformer(
        "TechWolf/JobBERT-v3"
    )
    print("JobBERT model loaded successfully")
except Exception as e:
    print("Failed to load JobBERT:", e)
    model = None


def get_semantic_score(
    resume_text: str,
    jd_text: str
):
    if model is None:
        return 0

    if not resume_text or not jd_text:
        return 0

    resume_embedding = model.encode(
        resume_text,
        convert_to_tensor=True
    )

    jd_embedding = model.encode(
        jd_text,
        convert_to_tensor=True
    )

    similarity = util.cos_sim(
        resume_embedding,
        jd_embedding
    ).item()

    score = similarity * 100

    return round(
        max(0, min(score, 100)),
        2
    )