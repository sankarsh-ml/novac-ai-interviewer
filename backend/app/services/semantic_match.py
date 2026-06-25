try:
    from sentence_transformers import SentenceTransformer, util
except Exception:
    SentenceTransformer = None
    util = None


_MODEL = None
_MODEL_LOAD_ATTEMPTED = False


def get_semantic_score(resume_text: str, jd_text: str) -> float:
    model = _get_model()

    if model is None or not resume_text or not jd_text:
        return 0

    resume_embedding = model.encode(resume_text, convert_to_tensor=True)
    jd_embedding = model.encode(jd_text, convert_to_tensor=True)
    similarity = util.cos_sim(resume_embedding, jd_embedding).item()
    return round(max(0, min(similarity * 100, 100)), 2)


def _get_model():
    global _MODEL
    global _MODEL_LOAD_ATTEMPTED

    if _MODEL_LOAD_ATTEMPTED:
        return _MODEL

    _MODEL_LOAD_ATTEMPTED = True

    if SentenceTransformer is None:
        return None

    try:
        _MODEL = SentenceTransformer("TechWolf/JobBERT-v3")
    except Exception as error:
        print(f"Failed to load JobBERT semantic model: {error}")
        _MODEL = None

    return _MODEL
