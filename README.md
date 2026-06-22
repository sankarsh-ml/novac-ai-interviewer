# AI Hiring / Resume Screener

## Main backend

```bat
cd D:\novac_3
venv\Scripts\activate
cd backend
uvicorn app.main:app --reload
```

## Frontend

```bat
cd D:\novac_3\frontend
npm run dev
```

## Indian ID validator

Aadhaar validation uses a separate Python environment at `D:\novac_3\id_venv`.
Even if the main backend `venv` has Paddle packages installed, the backend calls
the validator through subprocess and does not import `indian-id-validator\inference.py`
directly.

```bat
cd D:\novac_3
setup_id_venv.bat
```

## Test Indian ID validator

```bat
test_id_validator.bat "C:\Users\hp\OneDrive\Desktop\aadhar.png"
```

The backend defaults to:

```env
INDIAN_ID_PYTHON=D:\novac_3\id_venv\Scripts\python.exe
INDIAN_ID_INFERENCE=D:\novac_3\indian-id-validator\inference.py
```

These can be overridden in `.env`.

## Face verification

Install the main backend face verification dependencies in `venv`:

```bat
pip install insightface onnxruntime opencv-python numpy
```

Face verification uses InsightFace `buffalo_l` ArcFace embeddings on CPU. The
reference image priority is resume photo first, Aadhaar photo second. Live
webcam frames are compared with cosine similarity using a default threshold of
`0.38`, configurable with `FACE_VERIFY_THRESHOLD`.

Interview proceeds only after majority verification: 3 successful matches out
of 5 webcam frame attempts.

### Face health check

Start the backend using the active main backend venv:

```bat
cd D:\novac_3
venv\Scripts\activate
cd backend
python -m uvicorn app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/api/interview/face-health
```

Expected: `success` is `true` and `face_app` is `initialized`.

If `success` is `false`, read the exact `error` field.
