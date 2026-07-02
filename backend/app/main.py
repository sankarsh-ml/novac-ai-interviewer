from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.routes.ats_routes import router as ats_router
from app.routes.interview_routes import router as interview_router
from app.routes.job_routes import router as job_router
from app.routes.kyc_routes import router as kyc_router
from app.routes.question_bank_routes import router as question_bank_router
from app.routes.resume_routes import router as resume_router
from app.routes.admin_routes import router as admin_router
from app.routes.candidate_auth_routes import router as candidate_auth_router
from app.application.services.admin_service import require_admin_jwt, seed_default_admin
from app.infrastructure.database.mongo_service import DatabaseUnavailableError, close_mongo, get_database

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


admin_dependencies = [Depends(require_admin_jwt)]

app.include_router(resume_router, prefix="/api/resume", tags=["Resume"])
app.include_router(ats_router, prefix="/api/ats", tags=["ATS"], dependencies=admin_dependencies)
app.include_router(kyc_router, prefix="/api/kyc", tags=["KYC"])
app.include_router(interview_router, prefix="/api/interview", tags=["Interview"])
app.include_router(interview_router, prefix="/api/interviews", tags=["Interview"])
app.include_router(job_router, prefix="/api/hr", tags=["HR"], dependencies=admin_dependencies)
app.include_router(question_bank_router, prefix="/api/hr", tags=["Question Bank"], dependencies=admin_dependencies)
app.include_router(question_bank_router, prefix="/api", tags=["Question Bank"], dependencies=admin_dependencies)
app.include_router(admin_router)
app.include_router(candidate_auth_router)


@app.on_event("startup")
def startup_event():
    get_database()
    seed_default_admin()


@app.on_event("shutdown")
def shutdown_event():
    close_mongo()


@app.exception_handler(DatabaseUnavailableError)
def database_unavailable_handler(_request, _error):
    return JSONResponse(
        status_code=503,
        content={
            "success": False,
            "message": "Database unavailable. Please start MongoDB and try again.",
        },
    )

@app.get("/")
def root():
    return {
        "success": True,
        "message": "Resume Text Extraction API is running",
    }
