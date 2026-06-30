from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.ats_routes import router as ats_router
from app.routes.interview_routes import router as interview_router
from app.routes.job_routes import router as job_router
from app.routes.kyc_routes import router as kyc_router
from app.routes.question_bank_routes import router as question_bank_router
from app.routes.resume_routes import router as resume_router
from app.routes.admin_routes import router as admin_router

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
app.include_router(interview_router, prefix="/api/interviews", tags=["Interview"])
app.include_router(job_router, prefix="/api/hr", tags=["HR"])
app.include_router(question_bank_router, prefix="/api/hr", tags=["Question Bank"])
app.include_router(question_bank_router, prefix="/api", tags=["Question Bank"])
app.include_router(admin_router)

@app.get("/")
def root():
    return {
        "success": True,
        "message": "Resume Text Extraction API is running",
    }
