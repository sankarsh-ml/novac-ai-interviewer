def compare_faces(image_path_one: str | None, image_path_two: str | None) -> dict:
    if not image_path_one or not image_path_two:
        return {
            "status": "skipped_no_resume_photo",
            "score": None,
            "message": "Resume photo not available; photo matching skipped",
        }

    try:
        import cv2
        import insightface
    except Exception:
        return {
            "status": "unavailable",
            "score": None,
            "message": "Face matching not available yet",
        }

    try:
        app = insightface.app.FaceAnalysis(name="buffalo_l")
        app.prepare(ctx_id=-1)

        image_one = cv2.imread(image_path_one)
        image_two = cv2.imread(image_path_two)
        if image_one is None or image_two is None:
            return {
                "status": "unavailable",
                "score": None,
                "message": "Could not read one or both face images",
            }

        faces_one = app.get(image_one)
        faces_two = app.get(image_two)
        if not faces_one or not faces_two:
            return {
                "status": "unavailable",
                "score": None,
                "message": "Could not detect face in one or both images",
            }

        score = _cosine_similarity(faces_one[0].embedding, faces_two[0].embedding)
        return {
            "status": "passed" if score >= 0.5 else "failed",
            "score": round(float(score), 4),
            "message": "Resume photo matched Aadhaar photo" if score >= 0.5 else "Resume photo did not match Aadhaar photo",
        }
    except Exception:
        return {
            "status": "unavailable",
            "score": None,
            "message": "Face matching not available yet",
        }


def _cosine_similarity(vector_a, vector_b):
    dot_product = sum(float(a) * float(b) for a, b in zip(vector_a, vector_b))
    norm_a = sum(float(a) * float(a) for a in vector_a) ** 0.5
    norm_b = sum(float(b) * float(b) for b in vector_b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)
