import traceback
import uuid
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes.ats_routes import router as ats_router
from app.routes.candidate_routes import router as candidate_router
from app.routes.dev_routes import router as dev_router
from app.routes.interview_routes import router as interview_router
from app.routes.job_routes import router as job_router
from app.routes.kyc_routes import router as kyc_router
from app.routes.resume_routes import router as resume_router
from app.services.whisper_service import transcribe_audio


app = FastAPI(title="Resume Text Extraction API")


# Development CORS setup
# Allows React/Vite frontend running on localhost or 127.0.0.1 on any port.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(resume_router, prefix="/api/resume", tags=["Resume"])
app.include_router(ats_router, prefix="/api/ats", tags=["ATS"])
app.include_router(kyc_router, prefix="/api/kyc", tags=["KYC"])
app.include_router(interview_router, prefix="/api/interview", tags=["Interview"])
app.include_router(job_router, prefix="/api/hr", tags=["HR"])
app.include_router(candidate_router, prefix="/api/candidate", tags=["Candidate"])
app.include_router(dev_router, prefix="/api/dev", tags=["Development"])

BACKEND_DIR = Path(__file__).resolve().parents[1]
WHISPER_TEST_DIR = BACKEND_DIR / "uploads" / "whisper_tests"
WHISPER_TEST_TRANSCRIPT_DIR = WHISPER_TEST_DIR / "transcripts"
WHISPER_TEST_DIR.mkdir(parents=True, exist_ok=True)
WHISPER_TEST_TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/")
def root():
    return {
        "success": True,
        "message": "Resume Text Extraction API is running",
    }


@app.post("/test-whisper")
async def test_whisper(audio: UploadFile = File(...)):
    try:
        audio_bytes = await audio.read()

        if not audio_bytes:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "Empty audio file",
                },
            )

        suffix = Path(audio.filename or "").suffix.lower()
        audio_extension = suffix if suffix in {".webm", ".wav", ".mp3", ".m4a", ".ogg"} else ".webm"
        file_stem = uuid.uuid4().hex
        audio_path = WHISPER_TEST_DIR / f"{file_stem}{audio_extension}"
        transcript_path = WHISPER_TEST_TRANSCRIPT_DIR / f"{file_stem}.txt"

        audio_path.write_bytes(audio_bytes)
        transcript = transcribe_audio(str(audio_path))
        transcript_path.write_text(transcript, encoding="utf-8")

        return {
            "success": True,
            "transcript": transcript,
            "audio_file_path": str(audio_path),
            "transcript_file_path": str(transcript_path),
        }
    except Exception as error:
        print(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": str(error),
            },
        )
