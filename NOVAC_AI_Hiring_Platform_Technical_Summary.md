# NOVAC AI Hiring Platform - Complete Technical Summary

This markdown summary mirrors the generated PowerPoint structure and is based on analysis of the actual codebase under `D:\novac_3`.

Assumptions clearly applied:
- Liveness check is implemented.
- Completed interview reports can be downloaded.
- Current code search did not find a concrete report-download route; report download is documented as an assumed export layer over report-ready persisted data.

Total slides in companion deck: 84

## Title and Problem Statement

### Slide 1: NOVAC AI Hiring Platform

- AI-enabled hiring workflow for HR-led job setup, resume screening, identity verification, live interview, transcription, AI grading, and report download.
- Built as a React/Vite frontend plus FastAPI backend with local JSON/file persistence and model-backed service modules.
- Scope covers HR operations, candidate verification, interview execution, and post-interview review.
- Assumptions for this deck: liveness check is implemented; completed interview reports can be downloaded.

Callouts:
- Project: NOVAC AI Hiring Platform
- Audience: Project review / demo
- Source: Actual repo analysis

## Problem Statement

### Slide 2: The platform automates the slowest handoffs in early hiring.

- Manual resume screening is inconsistent and slow when many candidates apply for one role.
- Identity verification and interview scheduling often happen outside the ATS, creating fragmented records.
- Voice interviews require transcription, scoring, and HR review artifacts that are hard to standardize manually.
- NOVAC connects these stages into one application record keyed by application_id.

Flow: Resume intake -> ATS decision -> Identity verification -> Live interview -> AI grading -> HR report

## End-to-End Workflow

### Slide 3: Complete end-to-end workflow

- The HR path begins with job and question-bank setup; the candidate path begins only after an interview/verification link is generated.
- Each stage writes status and artifacts back to the same application record.
- Route guards prevent interview access until Aadhaar and face verification are complete.

Flow: HR creates job -> Uploads question bank -> Uploads resumes -> ATS scoring -> Shortlist -> Candidate link -> Aadhaar -> Face + liveness -> Interview -> Whisper -> Qwen grading -> HR report

## System Architecture

### Slide 4: System architecture separates UI workflow from model-backed services.

- React/Vite frontend controls page state, candidate route transitions, browser camera, microphone, and API calls.
- FastAPI exposes route groups under /api/resume, /api/ats, /api/kyc, /api/interview, and /api/hr.
- Service layer owns parsing, ATS scoring, local storage, KYC, face verification, Whisper, Qwen, and question-bank logic.
- Model layer includes JobBERT, Qwen through Ollama, Faster-Whisper, InsightFace buffalo_l, YOLO ID models, PaddleOCR, and OpenCV Haar cascades.
- Persistence is local JSON/files behind a Mongo-compatible db_service abstraction.

Flow: Browser -> React/Vite -> FastAPI routes -> Service layer -> Storage + model cache -> AI runtimes

### Slide 5: Runtime boundaries and model dependencies

- Ollama/Qwen runs as a local HTTP runtime at QWEN_BASE_URL, default http://127.0.0.1:11434.
- Indian ID validation runs outside the main backend venv through a subprocess using id_venv and indian-id-validator/inference.py.
- Whisper models are downloaded/cached under backend/models/whisper by faster-whisper.
- InsightFace initializes buffalo_l with CPUExecutionProvider and caches model files outside application JSON storage.
- Browser getUserMedia and MediaRecorder provide live frames and audio blobs to the backend.

| Boundary | Runtime | Used by |
| --- | --- | --- |
| Frontend | Browser + React | HR/candidate workflows |
| Backend | FastAPI + services | API orchestration |
| Ollama | Local HTTP | Qwen generation/grading |
| ID validator | Separate Python venv | Aadhaar OCR/classification |
| Model cache | Local disk | Offline model reuse |

## Frontend Modules

### Slide 6: Frontend routing is state-driven with candidate URL guards.

- App.jsx owns currentPage, selectedJob, applicationSummary, aadhaarSummary, camera stream, and candidate-loading state.
- Candidate URLs /verify/:id, /face-verification/:id, and /interview/:id are parsed on load.
- The app redirects candidates back to missing prerequisite steps if Aadhaar or face verification is incomplete.
- cameraSession is shared between face verification and interview to reuse/stop video streams cleanly.

Flow: /verify/:id -> Aadhaar page -> /face-verification/:id -> Face page -> /interview/:id -> Interview page

### Slide 7: HR dashboard creates job records that drive ATS scoring and question selection.

- HRDashboardPage fields: title, description, required skills, education, experience, keywords.
- Fetches existing jobs using GET /api/hr/jobs and creates new jobs using POST /api/hr/jobs.
- Required skills and keywords are comma-split into arrays before being sent to the backend.
- The resulting job id becomes the join key for applications and question banks.

| UI action | API | Backend storage |
| --- | --- | --- |
| Load jobs | GET /api/hr/jobs | jobs.json |
| Add job | POST /api/hr/jobs | new job id |
| Show job cards | state.jobs | title/skills/education/experience |

### Slide 8: Current Jobs is the HR navigation hub for each role.

- CurrentJobsPage loads all jobs and renders one card per job.
- Actions route HR to View Applications, Upload Resumes, Upload Question Bank, and View Question Bank.
- selectedJob is passed from App.jsx into downstream pages so every action is job-scoped.

Flow: Current Jobs -> View Applications -> Upload Resumes -> Question Bank -> Shortlisted Candidates

### Slide 9: Resume upload page supports multi-file ATS processing for HR.

- UploadResumePage accepts multiple PDF files, appends job_id, and sends FormData to POST /api/resume/bulk-upload.
- It shows selected files, upload progress, processed count, per-application status, duplicate flag, and failures.
- The backend scores each non-duplicate resume automatically during bulk upload.
- Failed files are returned in a failed array without stopping the whole batch.

| State | Purpose | Displayed |
| --- | --- | --- |
| files | Selected PDFs | file names + count |
| isUploading | Disable process button | Processing label |
| uploadResult | Backend response | processed/failed/duplicate rows |

### Slide 10: Single resume upload is available for candidate-style/manual flow.

- StudentUploadPage loads available jobs, requires job selection, validates PDF extension, and calls uploadResume(file, jobId).
- The upload API returns application_id, candidate info, file stats, and next_step=ats_screening.
- On success App.jsx moves to AtsScreeningPage, which calls GET /api/ats/score/{application_id}.

Flow: Select job -> Choose PDF -> POST /api/resume/upload -> ATS page -> Aadhaar if passed

### Slide 11: ATS screening page turns backend scoring into a candidate decision screen.

- AtsScreeningPage auto-runs scoring once an application_id is available.
- It displays candidate, ATS score, matched skill count, missing skill count, matched skills, and missing skills.
- Pass logic accepts backend passed/status or score >= 70.
- Passed candidates can continue to Aadhaar; failed candidates stop/back home.

| Input | API | Output shown |
| --- | --- | --- |
| application_id | GET /api/ats/score/{id} | ATS score/result |
| ats_result | frontend helpers | pass/fail banner |
| matched/missing skills | response result | skill chips |

### Slide 12: Question Bank page manages HR-authored interview content.

- Supports text file upload and manual question creation.
- Manual fields include question, expected_answer, difficulty, and category.
- Fetches uploaded questions using GET /api/hr/jobs/{job_id}/question-bank.
- Saves manual banks with POST /api/hr/question-bank/save and text files with POST /api/hr/question-bank/upload.
- Displays saved questions, difficulty, category, and expected answers for HR verification.

Flow: Manual/file input -> Normalize -> Save by job_id -> Review uploaded bank -> Interview uses bank first

### Slide 13: Shortlisted Candidates page creates the candidate verification link.

- Filters job applications to ATS-passed candidates.
- HR selects an expiry date before link generation.
- POST /api/interview/create-link writes token JSON, stores verification_link/interview_token, and returns verification/interview URLs.
- Completed interviews cannot generate a new link from this page.
- Generated link is copied to clipboard for sharing.

| UI state | Meaning |
| --- | --- |
| expiryDates | per-application selected expiry |
| generatedLinks | verification links by application_id |
| applications | ATS-passed candidates for job |

### Slide 14: Aadhaar verification page gates identity before live face checks.

- Accepts .jpg, .jpeg, .png, and .pdf files.
- Calls POST /api/kyc/aadhaar/upload/{application_id}.
- Displays resume name, Aadhaar name, name match score, photo stored, photo match, and masked Aadhaar.
- On success updates App state to aadhaarVerified and routes to /face-verification/{application_id}.

Flow: Select file -> Upload Aadhaar -> Backend OCR/name match -> Show verification -> Continue face

### Slide 15: Face verification page captures live frames and saves verification status.

- Starts browser camera through the shared cameraSession.
- Captures the current video frame to a JPEG blob using canvas.
- Sends the frame to POST /api/interview/face-verify/{application_id}.
- On match, calls POST /api/kyc/verification/mark/{application_id} to persist verified status.
- Current UI needs one successful match; deck assumes liveness challenge/check is implemented.

| State | Purpose |
| --- | --- |
| attempts | frame attempts; UI shows /5 |
| matches | successful matches; UI shows /1 |
| lastResult | backend face match message/score |
| status | idle/ready/verifying/failed/passed |

### Slide 16: Interview page enforces camera-visible, voice-only answering.

- InterviewPage requires Aadhaar and face verification before starting.
- It loads questions from POST /api/interview/{application_id}/start.
- Camera remains visible during interview; audio recording is separate from video stream.
- Candidate records voice answers only; transcript textarea is read-only after Whisper transcription.
- Each answer is submitted to Qwen grading; final interview completion stops camera and shows Interview Over.

Flow: Verified candidate -> Start interview -> Question -> Record voice -> Whisper transcript -> Submit -> Qwen grade -> Next/finish

### Slide 17: Candidate details view is the current report-ready HR review surface.

- JobApplicationsPage table displays ATS, semantic, skill, education, experience, project, verification, interview, and link status.
- CandidateDetailsPanel displays ATS score, interview score, question source, and interview status.
- For each answer it shows question, expected answer when from question bank, transcript, audio path, rubric scores, feedback, missing points, and submitted timestamp.
- Report download is assumed implemented as an export layer over this stored data.

| Report field | Current source |
| --- | --- |
| Candidate/name/email | application record |
| ATS metrics | ats_result + stored scores |
| Transcripts/audio | interview_answers |
| Rubric/feedback | Qwen grading record |

## Backend Routes

### Slide 18: FastAPI main app exposes six route groups under localhost-friendly CORS.

- app.main creates FastAPI(title='Resume Text Extraction API').
- CORS allows React/Vite origins on localhost or 127.0.0.1 at any port.
- Routers: resume, ATS, KYC, interview, HR/jobs, question bank.
- Root GET / returns a running status message.

| Prefix | Router | Primary responsibility |
| --- | --- | --- |
| /api/resume | resume_routes | upload/extract resumes |
| /api/ats | ats_routes | score/save ATS decision |
| /api/kyc | kyc_routes | Aadhaar + verification status |
| /api/interview | interview_routes | links, face, questions, transcription, grading |
| /api/hr | job_routes + question_bank_routes | jobs, applications, banks |

### Slide 19: HR/job routes own job and application listing/deletion.

- POST /api/hr/jobs accepts title, description, required_skills, education, experience, keywords.
- GET /api/hr/jobs returns all jobs from jobs.json.
- GET /api/hr/applications and /api/hr/jobs/{job_id}/applications return application records.
- DELETE /api/hr/applications/{application_id} deletes the application and local owned artifacts.
- Errors: missing application returns 404.

| Endpoint | Service | Storage updated/read |
| --- | --- | --- |
| POST /jobs | save_job | jobs.json |
| GET /jobs | get_all_jobs | jobs.json |
| GET /jobs/{id}/applications | list_applications filter | applications.json |
| DELETE /applications/{id} | delete_application | JSON + candidate files |

### Slide 20: Resume routes create application records and start ATS in bulk mode.

- POST /api/resume/upload accepts resume_file or file plus optional job_id.
- POST /api/resume/bulk-upload accepts job_id and resumes[]; each non-duplicate resume is scored.
- POST /api/resume/extract-text extracts text without creating a full application.
- Only PDF files are accepted; unreadable PDFs return 400.
- Duplicate detection uses SHA-256 resume hash within the same job_id.

| Endpoint | Request | Response highlights |
| --- | --- | --- |
| /upload | file, job_id | application_id, stats, next_step |
| /bulk-upload | job_id, resumes[] | processed, failed, duplicate |
| /extract-text | file | text + ats_ready_data |

### Slide 21: ATS routes compute and persist screening scores.

- GET /api/ats/score/{application_id} fetches application and job, prepares resume_data from parsed sections, calls calculate_ats, and updates the application.
- POST /api/ats/{application_id}/decision stores manual passed/failed decisions.
- 404 if application or job is missing; 400 if manual decision is not passed/failed.
- Response includes ats_score, matched_skills, missing_skills, status, passed, and next_step.

Flow: application_id -> get application -> get job -> calculate_ats -> update_application -> return decision

### Slide 22: Question bank routes persist job-wise interview questions.

- POST /api/hr/question-bank/save accepts job_id and a list of QuestionItem objects.
- POST /api/hr/question-bank/upload accepts job_id and a text file; parser supports delimited and plain-text formats.
- GET /api/hr/question-bank/{job_id} and /api/hr/jobs/{job_id}/question-bank return normalized questions.
- Storage path: backend/app/storage/question_banks/{job_id}.json.

| Field | Meaning |
| --- | --- |
| question | candidate-facing prompt |
| expected_answer | used in HR review and Qwen grading |
| difficulty | Easy/Medium/Hard |
| category | skill/category/topic label |

### Slide 23: KYC/Aadhaar routes validate candidate identity after ATS pass.

- GET /api/kyc/candidate/{application_id} returns candidate verification payload.
- GET /api/kyc/verification-status/{application_id} returns Aadhaar/face/interview status flags.
- POST /api/kyc/aadhaar/upload/{application_id} validates file extension, saves to candidate/aadhaar, and calls verify_aadhaar_for_application.
- POST /api/kyc/verification/mark/{application_id} persists final verified state after face/liveness.
- Failures return JSONResponse with status_code, success=false, message, and next_step/debug data where available.

| Storage updated | Keys |
| --- | --- |
| KYC result | aadhaar_verification, kyc_verification |
| Application flags | aadhaarVerified, faceVerified, verification_status |
| Artifacts | aadhaar_image_path, aadhaar_face_image_path |

### Slide 24: Face verification and liveness routes live in the interview route group.

- POST /api/interview/face-verify/{application_id} saves a live frame and compares it against a reference face.
- Reference selection in code checks Aadhaar face candidates first, then resume face candidates, then generic candidate image paths.
- GET /api/interview/face-health checks insightface, onnxruntime, cv2, numpy and FaceAnalysis initialization.
- Assumed liveness layer runs around/with frame capture before mark verified is saved.
- Error cases: missing application, no reference face, empty frame, no detected face, import/model failure.

Flow: Webcam frame -> save live frame -> select reference -> InsightFace embeddings -> cosine threshold -> mark verified

### Slide 25: Interview routes manage links, question loading, answers, and completion.

- POST /api/interview/create-link creates token JSON, expiry date, verification URL, interview URL, and stores link fields on application.
- GET /api/interview/validate-token/{token} checks token existence, application, used flag, completion, and expiry.
- POST /api/interview/{application_id}/start requires Aadhaar and face verification, then prepares/stores questions and sets status in_progress.
- POST /api/interview/questions/{application_id}/complete requires every question answer to be Qwen-graded before completion.
- Completion writes interview_score, interview_completed_at, and marks link token used.

| Step | Guard |
| --- | --- |
| Create link | application exists and not completed |
| Validate link | not expired, not used, not completed |
| Start | Aadhaar + face verified |
| Complete | all answers graded |

### Slide 26: Transcription route stores audio before invoking Whisper.

- POST /api/interview/{application_id}/transcribe accepts audio upload.
- Requires candidate verification before transcription.
- Saves audio under candidate_folder/interview_audio/{uuid}.{extension}.
- Allowed extensions: .webm, .wav, .mp3, .m4a, .ogg, .mp4; fallback extension is .webm.
- Returns transcript, audioPath/audio_path, and selected Whisper model.

Flow: audio blob -> validate candidate -> save file -> transcribe_audio -> return transcript + path

### Slide 27: Qwen grading route persists detailed rubric records.

- POST /api/interview/questions/{application_id}/evaluate accepts question_id, answer_text, transcript, and audio_path.
- Finds the question in stored interview_questions and calls evaluate_answer_with_qwen.
- Builds an answer record containing transcript, audio path, grading status, scores, feedback, missing points, model, and timestamp.
- Updates interview_answers and rolling interview_score.
- If Qwen is unavailable or JSON is invalid after repair/regrade, response is 502 and gradingStatus=grading_failed.

| Saved field | Meaning |
| --- | --- |
| finalScore | 0-10 final mark |
| relevance/technical/depth/clarity | rubric marks |
| feedback | Qwen evaluator comments |
| missingPoints | gaps identified |
| gradingModel | Qwen/Ollama model name |

### Slide 28: Report download route is assumed, not present in current code search.

- Current code exposes report-ready data through GET application routes and JobApplicationsPage CandidateDetailsPanel.
- No concrete /report/download, /export, PDF, or CSV route was found in backend/app routes.
- Per user instruction, this deck assumes completed interview reports can be downloaded.
- Recommended implementation: GET /api/hr/applications/{application_id}/report?format=pdf|csv|json after interview_completed=true.
- Report generation should read application record, interview_answers, ATS result, verification status, and artifact paths.

| Assumed endpoint | Required guard | Output |
| --- | --- | --- |
| /api/hr/applications/{id}/report | interview_completed | PDF/CSV/JSON |
| Source data | application record | ATS + KYC + answers |
| Failure | missing/unfinished record | 404/409 |

## Resume Upload and Parsing

### Slide 29: Resume upload creates a per-candidate artifact folder and normalized ATS payload.

- A new UUID application_id is generated before parsing.
- Resume PDF is saved under storage/candidates/{application_id}/resumes with a UUID-prefixed filename.
- SHA-256 file hash supports duplicate detection for the same job.
- PyMuPDF extracts ordered text from PDF pages.
- Text is cleaned, sectioned, and stored as ats_ready_data with raw_text, normalized_text, and sections_detected.

Flow: UploadFile -> application UUID -> save PDF -> hash -> PyMuPDF -> clean text -> sections -> save app

### Slide 30: Resume parser converts raw PDF text into education, skills, projects, and experience.

- Header normalization recognizes spaced headings such as E DUCATION and T ECHNICAL S KILLS.
- Education parser extracts degree, institution, duration, grade, and school/board records.
- Experience parser detects company/title/duration, location, bullets, technologies, and duration_months.
- Project parser detects project title, description, bullets, technologies, and links.
- Skills parser splits compact skill lines by commas, pipes, semicolons, bullets, and newlines.

| Section | Extraction method |
| --- | --- |
| Candidate name | first clean line that looks like a name |
| Email | regex in resume text |
| Education | degree/institution/date/grade regex |
| Experience | date ranges + role/company heuristics |
| Projects | title and technology heuristics |
| Skills | short skill tokens + dedupe |

### Slide 31: Resume photo extraction supports later face verification.

- extract_resume_photo scans embedded PDF images larger than 5000 bytes.
- If OpenCV is available, Haar cascade detects the largest frontal face and writes a cropped resume_face image.
- If no face is detected or OpenCV path fails, it stores the embedded photo image as a fallback.
- Application stores resume_photo_path, resume_face_image_path, and candidate_image_path.
- Failure to find a photo is not fatal; Aadhaar photo may become the face reference.

Flow: PDF image xref -> extract bytes -> OpenCV decode -> Haar face crop -> resume_face path

### Slide 32: Resume upload failure and duplicate handling

- Non-PDF uploads return HTTP 400: Only PDF files are allowed.
- Unreadable PDFs remove the saved file and return HTTP 400: Unable to read the PDF file.
- Duplicate files are detected by resume_file_hash plus job_id; duplicate temp artifacts are deleted.
- Bulk upload records failed files independently and can return partial_success.
- ATS failures during bulk upload mark that item processing_status=ats_failed with an error message.

| Failure | Handling |
| --- | --- |
| Wrong extension | 400 before save |
| Empty/invalid PDF | saved file removed |
| Duplicate | candidate folder removed; original app returned |
| ATS job missing | ats_failed in bulk item |

## ATS Scoring

### Slide 33: ATS engine blends semantic relevance, explicit skills, education, experience, and projects.

- ats_routes builds resume_data from the stored application sections and job data from jobs.json.
- calculate_ats calls keyword_match, education_match, experience_match, project_quality, and semantic_match.
- Shortlist threshold is 70; status is passed when ats_score >= 70.
- Scores and matched/missing skills are persisted back to the application.
- Calibration limitation: active score weights sum to 1.20, so final score can need normalization/tuning.

| Component | Weight in active engine |
| --- | --- |
| Semantic score | 0.35 |
| Skill score | 0.45 |
| Education score | 0.10 |
| Experience score | 0.15 |
| Project score | 0.15 |

### Slide 34: Semantic score uses JobBERT embeddings for resume-to-job relevance.

- Input resume text is a semantic corpus of skills, experience titles/descriptions, and project titles/descriptions.
- Job text is job description or title.
- Model: SentenceTransformer('TechWolf/JobBERT-v3').
- Output: cosine similarity scaled to 0-100 and clipped to [0, 100].
- If sentence-transformers or model load fails, semantic score returns 0.
- First load may require internet; offline after model is cached.

Flow: resume corpus -> JobBERT encode -> job encode -> cosine similarity -> semantic_score

### Slide 35: Skill score uses alias-aware exact matching across raw and extracted text.

- Inputs: job.required_skills, raw resume text, and parsed skills section.
- Aliases cover C++, JavaScript/JS, FastAPI, MongoDB, SQL variants, AI/ML, OpenCV, PaddleOCR, React, Node.js, REST API, and more.
- Score = matched required skills / total required skills * 100.
- Outputs matched_skills and missing_skills for HR review.
- Fully offline after code/package install; no model dependency.

| Example canonical | Aliases |
| --- | --- |
| javascript | javascript, java script, js |
| mongodb | mongodb, mongo db |
| scikit-learn | scikit-learn, scikit learn, sklearn |
| rest api | rest api, rest apis, restful api, rest |

### Slide 36: Education score checks degree level and branch relevance.

- Inputs: parsed education items and job.education requirement.
- Detects school, diploma, bachelor's, master's, engineering requirement, and branches such as CS, IT, AI/ML, ECE, EEE, Mechanical, Civil.
- Exact text match gives 100; matching bachelor's gives 100; related engineering branch gives 85; different specialization can still score 75.
- Master's required but bachelor's found scores 60; school-only education scores 20.
- Output includes score, matched flag, best degree, and reason.

| Case | Score behavior |
| --- | --- |
| No requirement | 100 |
| Matching degree/branch | 100 |
| Related engineering branch | 85 |
| Different bachelor's specialization | 75 |
| Only school-level | 20 |

### Slide 37: Experience score converts parsed durations into years.

- Inputs: parsed experience entries and job.experience years.
- Each experience item contributes duration_months or extracted months from text like 'Jan 2024 - Present'.
- If required experience is 0, score is 100.
- If candidate years >= required, score is 100.
- If candidate has some experience but below requirement, score is max(50, ratio * 100).
- Output includes score and years.

Flow: experience items -> duration months -> total years -> compare required years -> experience_score

### Slide 38: Project score rewards both quantity and job relevance.

- Inputs: parsed projects, job required skills, keywords, and job title.
- Long experience descriptions can be treated as project-like evidence.
- Quantity score: 5+ projects = 100, 3-4 = 75, otherwise 50.
- Quality score: matched targets / total targets * 100, capped at 100.
- Final project score = 0.4 quantity + 0.6 quality.
- Output includes project_count, matched keywords, quantity_score, quality_score, and score.

| Signal | Meaning |
| --- | --- |
| required_skills | technical relevance |
| keywords | role/domain relevance |
| job_title | role relevance |
| technologies | project stack match |

### Slide 39: ATS output becomes the gate to KYC.

- Result status is passed or failed.
- Stored fields: ats_status, ats_decision, ats_result, ats_score, matched_skills, missing_skills, semantic_score, skill_score, education_score, experience_score, project_score.
- Response next_step is aadhaar_verification only if passed; otherwise stop.
- HR can view all component scores in JobApplicationsPage.

Flow: ATS result -> persist component scores -> passed? -> Aadhaar verification -> or stop

## Question Bank

### Slide 40: Question bank parser supports HR-authored files and manual entries.

- Question bank is saved per job_id under backend/app/storage/question_banks/{job_id}.json.
- Plain text parser supports Q:/A:, ANS:, ANS:=, ANSWER:, EXPECTED_ANSWER:, and numbered question prefixes.
- Delimited parser uses csv.Sniffer and DictReader for comma or tab separated files.
- Normalization maps expectedAnswer/answer/ANS aliases to expected_answer.
- Difficulty defaults to Medium unless Easy/Medium/Hard is supplied.
- Category defaults to Question Bank if category/skill/topic is absent.

| Input format | Supported fields |
| --- | --- |
| Manual UI | question, expected_answer, difficulty, category |
| TXT Q/A | Q: question + A:/ANS:= answer |
| CSV/TSV | question, expected_answer/answer, difficulty, category/skill/topic |

### Slide 41: Interview question loading prefers question bank content.

- Interview start calls _prepare_interview_questions in interview_routes.
- If a current question payload exists and still matches the contract, it is reused.
- If a question bank exists for the job, questions are normalized and stored as source=question_bank.
- If no bank exists in this route path, result source=none, status=empty, questions=[].
- question_generation_service can generate Qwen questions on regenerate or alternate service usage, but start currently loads bank-first in routes.

Flow: Start interview -> load bank by job_id -> normalize -> store interview_questions -> frontend renders questions

## Qwen Question Generation

### Slide 42: Qwen question generation uses resume and job context when no bank is selected by the generation service.

- generate_interview_questions first checks for a job-specific question bank; if present, Qwen is skipped.
- If no bank and USE_QWEN is false, rule-based fallback questions are returned.
- If USE_QWEN is true, it calls Qwen through Ollama with strict JSON requirements.
- Prompt inputs include job title, description, required skills, education, experience, keywords, parsed skills, common skills, projects, experience, education, ATS result, matched/missing skills, and resume text up to 12000 characters.

Flow: application -> resume context -> job context -> ATS context -> Qwen prompt -> JSON questions

### Slide 43: Qwen question schema requires exactly five balanced questions.

- Required split: 2 Easy, 2 Medium, 1 Hard.
- Required categories: Resume Overview, Project-Based Technical, Skill-Based Technical, System Design/Architecture/Debugging, Behavioral/HR/ATS Gap.
- Schema: candidate_name plus questions array with id, category, difficulty, question, expected_focus.
- Post-processing deduplicates, enforces difficulty split, limits repeated categories, and fills gaps with fallback questions.
- If Qwen returns unusable JSON, generation returns success=false for Qwen path rather than silently inventing Qwen content.

| Question id | Target |
| --- | --- |
| q1 | Resume overview |
| q2 | Project based |
| q3 | Skill technical |
| q4 | System design/debugging |
| q5 | Behavioral/HR gap |

## Qwen Runtime

### Slide 44: Qwen service wraps Ollama with strict JSON parsing and retries.

- Default base URL: http://127.0.0.1:11434.
- Default model: qwen2.5:7b.
- call_qwen posts to /api/generate with stream=false, temperature/top_p/num_predict options, and format=json when requested.
- If json mode fails with HTTP >= 400, it retries without the format field.
- call_qwen_json parses JSON, then retries once with a stricter 'return only JSON' prompt if needed.
- Health check GET /api/tags verifies the configured model is pulled and available.

| Env var | Default |
| --- | --- |
| QWEN_BASE_URL | http://127.0.0.1:11434 |
| QWEN_MODEL | qwen2.5:7b |
| USE_QWEN | true |
| QWEN_TIMEOUT_SECONDS | 90 in code |

## Qwen Answer Grading

### Slide 45: Qwen grading is the only answer scoring method.

- evaluate_answer_with_qwen never uses a deterministic fallback score.
- If Qwen is unavailable or returns invalid grading, the saved answer has gradingStatus=grading_failed and the API asks the candidate to retry.
- The candidate does not see rubric scores during interview; frontend only shows successful submission.
- HR views grading later in CandidateDetailsPanel/report.

Flow: transcript -> Qwen health -> grading prompt -> parse/repair/regrade -> save answer record -> HR review

### Slide 46: Qwen grading prompt contains question, expected answer, transcript, resume, and job context.

- Inputs: application, question object, transcript/answer_text, question_index, question_source.
- Prompt includes job role/title, required skills, resume context, question object, expected answer, and candidate transcript.
- Scores must be 0-10 and include finalScore, relevance, technical, depth, clarity, feedback, and missingPoints.
- Expected answer is used strongly for question bank questions but exact wording is not required.

| Prompt input | Source |
| --- | --- |
| Question | interview_questions |
| Expected answer | question bank / question payload |
| Transcript | Whisper result |
| Resume context | application sections/text |
| Job context | jobs.json + application |

### Slide 47: Qwen grading parser repairs common LLM output problems.

- First tries direct JSON parse.
- Then extracts a JSON object from fenced/prose output using raw_decode or first/last braces.
- Normalizes aliases such as final_score, score, overallScore, technical_accuracy, missing_points.
- Validates required keys, numeric range 0-10, non-empty feedback, and no 'not available' placeholders.
- If invalid, Qwen is asked to repair the JSON without grading again.
- If all scores are zero but feedback sounds positive, Qwen is asked to regrade from scratch.

Flow: raw Qwen response -> direct parse -> extract JSON -> normalize aliases -> validate -> repair/regrade -> graded/fail

### Slide 48: Qwen grading records are report-ready.

- Answer record stores questionId, question text, expectedAnswer, difficulty, skill/category, answerText, transcript, audioPath, evaluation, gradingStatus, gradingModel, submittedAt.
- Successful grading also stores score/finalScore, relevance, technical, depth, clarity, feedback, missingPoints, and nested grading.
- Application interview_score is updated as the average of graded answer scores.
- Interview completion requires every question answer to exist and have gradingStatus=graded.

| Saved group | Fields |
| --- | --- |
| Identity | questionId, submittedAt |
| Answer | answerText, transcript, audioPath |
| Rubric | finalScore, relevance, technical, depth, clarity |
| Feedback | feedback, missingPoints |
| Model | gradingModel, base_url/json_mode metadata |

## Aadhaar/KYC Verification

### Slide 49: Aadhaar verification only starts after ATS pass.

- verify_aadhaar_for_application rejects applications whose ats_status is not passed.
- Allowed upload extensions: .jpg, .jpeg, .png, .pdf.
- The uploaded file is stored under storage/candidates/{application_id}/aadhaar.
- PDF Aadhaar files are converted to page1 JPEG before model validation.
- Aadhaar validator timeout is 90 seconds.

Flow: ATS passed -> Aadhaar file -> save candidate/aadhaar -> prepare image -> ID validator -> fields + photo

### Slide 50: Indian ID validator detects Aadhaar and extracts fields through a subprocess.

- Backend calls id_venv/Scripts/python.exe indian-id-validator/inference.py instead of importing it directly.
- classify_only first tries the ID classifier; if it fails, Aadhaar detection is attempted as fallback.
- Field extraction flattens validator output and searches for name, DOB, gender, Aadhaar number/UID/id_number.
- Aadhaar number is masked before storage/logging as XXXX XXXX last4.
- Raw output is sanitized to mask Aadhaar-like patterns.

| Model file | Purpose |
| --- | --- |
| Id_Classifier.pt | document type classification |
| Aadhaar_Card.pt | Aadhaar field detection |
| Pan_Card.pt | PAN support in validator |
| Passport.pt | Passport support in validator |
| Voter_Id.pt | Voter ID support |
| Driving_License.pt | Driving license support |

### Slide 51: Aadhaar name matching combines sequence and token-initial logic.

- Resume name comes from candidate_name fields or first plausible resume text line.
- Aadhaar name comes from extracted name/full_name/aadhaar_name/applicant_name/holder_name fields.
- Names are normalized by removing non-letters and collapsing spaces.
- Similarity is max(SequenceMatcher ratio, token-initial match score).
- Threshold NAME_MATCH_THRESHOLD = 0.70.
- If name fails, verification_status=aadhaar_failed and next_step=recapture.

Flow: resume name -> aadhaar name -> normalize -> sequence/token score -> >=0.70? -> aadhaar_passed/failed

### Slide 52: Aadhaar photo extraction creates the reference used by live verification.

- extract_aadhaar_photo uses OpenCV Haar cascade to crop the largest face from the Aadhaar image.
- If no face is detected, the uploaded Aadhaar image is copied as a development fallback reference.
- Stored fields include aadhaar_photo_path and aadhaar_face_image_path.
- A static photo_match between resume and Aadhaar photos is attempted with InsightFace but nonavailability is tolerated.
- Final Aadhaar success returns next_step=face_verification while faceVerified remains false.

| Success stores | Meaning |
| --- | --- |
| aadhaar_extracted_name | OCR name |
| aadhaar_image_path | uploaded original |
| aadhaar_photo_path | cropped/fallback face |
| aadhaarVerified | true when name passes |
| verification_status | aadhaar_passed |

## Face Verification and Liveness

### Slide 53: Face verification compares live frame embeddings to identity references.

- Frontend captures a webcam frame to JPEG; backend stores it in storage/live_frames.
- Reference priority required for this deck: Aadhaar face, then resume face, then candidate image.
- Code currently checks Aadhaar candidates first in _find_reference_face_path, then resume candidates, then candidate image candidates.
- Model: InsightFace FaceAnalysis(name='buffalo_l') with CPUExecutionProvider.
- Largest detected face embedding is compared with cosine similarity.
- Default threshold FACE_VERIFY_THRESHOLD=0.38.

Flow: reference face -> live frame -> InsightFace embeddings -> cosine score -> threshold -> match

### Slide 54: Liveness check is assumed active before final verification.

- Assumption: liveness/anti-spoofing challenge is implemented around the live frame workflow.
- Expected flow: camera permission -> live challenge -> frame capture -> backend face match -> liveness pass -> mark verified.
- Current UI persists one successful match as enough to proceed; README also discusses majority verification in a 5-frame attempt policy.
- Deck follows the user requirement: one successful match is enough to proceed, with liveness assumed implemented.
- Persisted status includes live_face_verification with status, reference_source, score, attempts, matches, required_matches, verified_at.

| Integrity signal | Purpose |
| --- | --- |
| Camera permission | live user presence |
| Liveness challenge | anti-spoofing |
| Face cosine score | identity match |
| Attempts/matches | audit trail |
| verification_completed | interview gate |

## Interview Pipeline

### Slide 55: Interview route guard requires Aadhaar and face verification.

- Both start_interview and get_interview_questions call _is_interview_access_verified.
- Aadhaar verified is true if aadhaarVerified/aadhaar_verified or verification_status is aadhaar_passed/verified.
- Face verified is true if faceVerified/face_verified, live_face_verification.status=passed, or verification_status=verified.
- Unverified candidates receive HTTP 403 and cannot load interview questions.
- Completed interviews return status=completed and no questions.

Flow: candidate URL -> load status -> aadhaar? -> face? -> start interview -> or redirect/403

### Slide 56: Interview question source is visible and stored.

- Question source can be question_bank, qwen, rule_based_fallback, or none depending on route/service path.
- In the active start route, job-specific question bank is the intended source.
- Frontend displays source text: Question Bank, Generated by Qwen, or Prepared by fallback engine.
- Question payload stores question_bank_id, question_bank_name, question_source, and normalized questions.
- If no questions are returned, frontend shows a question-generation error.

| Source | How selected |
| --- | --- |
| question_bank | load_question_bank(job_id) succeeds |
| qwen | generation service with USE_QWEN true |
| rule_based_fallback | USE_QWEN false or fallback path |
| none | no question bank in active route |

### Slide 57: Voice-only answer mode protects interview integrity.

- Candidate cannot type answers directly; transcript textarea is read-only.
- MediaRecorder captures audio chunks from a microphone stream.
- After recording stops, audio blob is uploaded to the backend for Whisper transcription.
- Transcript must be non-empty before Submit Answer is enabled.
- After submit, the current answer cannot be resubmitted; candidate proceeds to next question or finish.

Flow: Start recording -> Stop -> Upload audio -> Whisper transcript -> Read-only transcript -> Submit answer

### Slide 58: Completing the interview requires all Qwen grades.

- complete_interview reads stored interview_questions and interview_answers.
- Any missing or ungraded answer causes HTTP 400: All answers must be graded by Qwen.
- Average interview_score is computed from graded answer scores.
- Completion writes interview_status=completed, interview_completed=true, interview_score, interview_completed_at, completedAt.
- If an interview token exists, the link JSON is marked used=true.

Flow: all questions -> all graded? -> average score -> mark completed -> mark link used -> HR review/report

## Camera and Microphone Handling

### Slide 59: Camera and microphone streams are intentionally separate.

- Camera stream is video-only and reused by FaceVerificationPage and InterviewPage via cameraSession.
- Microphone stream is requested only when recording an answer.
- Audio tracks are stopped after each recording; camera can remain active during interview.
- Browser APIs: navigator.mediaDevices.getUserMedia, MediaRecorder, canvas.toBlob.
- Failure handling includes camera permission denied, camera warming up/no video size, microphone unavailable, MediaRecorder unsupported, empty audio, and no transcript.

| Browser API | Used for |
| --- | --- |
| getUserMedia({video:true}) | face/interview camera |
| canvas.drawImage + toBlob | live frame JPEG |
| getUserMedia({audio:true}) | answer recording |
| MediaRecorder | audio chunks/blob |
| sendBeacon | attempt completion on page unload |

## Whisper Transcription

### Slide 60: Whisper transcription runs locally after model cache is available.

- Module: backend/app/services/whisper_service.py.
- Library: faster-whisper.
- Default model: medium; fallback order includes medium, small, base.
- Default model directory: backend/models/whisper.
- Default device: cpu; default compute type: int8.
- Audio input is a saved file path; output includes transcript, language, and model name.
- First model load can download model files; offline after cache.

| Env var | Default / behavior |
| --- | --- |
| WHISPER_MODEL | medium |
| WHISPER_MODEL_DIR | backend/models/whisper |
| WHISPER_DEVICE | cpu |
| WHISPER_COMPUTE_TYPE | int8 |
| Fallback | small, base if preferred fails |

### Slide 61: Whisper route failure cases are user-recoverable.

- Missing saved audio file returns success=false with 'Audio file was not saved correctly'.
- Missing faster-whisper package raises a runtime error and returns transcription failure.
- Model load failure tries fallback models before raising Could not load Whisper transcription model.
- Empty transcript triggers frontend voiceError asking the candidate to record again.
- CPU/int8 keeps demo setup simpler but can be slower for medium model on limited hardware.

Flow: audio saved? -> model load -> transcribe -> non-empty transcript? -> submit answer

## Storage and Persistence

### Slide 62: Storage is local JSON plus candidate artifact folders.

- db_service is a compatibility layer; MongoDB is no longer used in this codebase.
- application_store_service owns create/update/list/delete operations with a threading lock.
- applications.json stores application records, ATS results, verification flags, interview questions, answer records, scores, and artifact paths.
- jobs.json stores role definitions.
- question_banks/{job_id}.json stores HR-authored questions.

| Storage | Path |
| --- | --- |
| Applications | backend/app/storage/applications.json |
| Jobs | backend/app/storage/jobs.json |
| Question banks | backend/app/storage/question_banks/{job_id}.json |
| Interview links | backend/app/storage/interview_links/{token}.json |

### Slide 63: Candidate folder keeps all uploaded and generated artifacts together.

- Candidate root: backend/app/storage/candidates/{application_id}.
- Resume PDFs: candidates/{id}/resumes.
- Resume face/photo: candidates/{id}/resume_faces.
- Aadhaar files: candidates/{id}/aadhaar.
- Aadhaar faces: candidates/{id}/aadhaar_faces.
- Interview audio: candidates/{id}/interview_audio.
- Live face frames are stored under storage/live_frames.

Flow: candidate folder -> resumes -> resume_faces -> aadhaar -> aadhaar_faces -> interview_audio

### Slide 64: Application records are the project backbone.

- Initial upload creates identity, file, resume, KYC, face, and interview status fields.
- ATS updates component scores and decision fields.
- KYC updates Aadhaar fields, masked ID, reference photo paths, and verification flags.
- Face verification updates live_face_verification and final verification status.
- Interview updates questions, answers, grading, score, completion timestamps, and used link token.

| Stage | Key fields |
| --- | --- |
| Upload | application_id, job_id, candidate_name, email, file_path |
| ATS | ats_score, matched_skills, component scores |
| KYC | aadhaarVerified, masked_aadhaar_number, aadhaar_face_image_path |
| Face | faceVerified, live_face_verification |
| Interview | interview_questions, interview_answers, interview_score |

### Slide 65: Runtime storage and model caches should not be committed.

- Recommended Git ignores: backend/app/storage/candidates, live_frames, aadhaar, resumes, resume_photos, aadhaar_photos, question_banks if demo data is private, interview_links, interview_audio.
- Model caches should be ignored: backend/models/huggingface, backend/models/whisper, InsightFace model cache, Ollama model store.
- Uploaded PDFs, Aadhaar images, audio files, transcripts, and generated reports may contain sensitive personal data.
- Local JSON files are useful for demos but should migrate to production storage with access controls and audit logs.

| Ignore category | Reason |
| --- | --- |
| model caches | large generated/downloaded files |
| uploads/runtime storage | private candidate data |
| audio/transcripts | sensitive interview data |
| reports | sensitive HR artifacts |

## Downloadable Reports

### Slide 66: Completed interview reports become available only after interview completion.

- Assumption: downloadable report export is implemented.
- Availability guard should be interview_completed=true and all answers graded.
- Report source is the persisted application record plus linked local artifacts.
- HR workflow: Job Applications -> View candidate details -> Download completed interview report.
- Suggested formats: PDF for review/demo, CSV for HR spreadsheet workflows, JSON for system integration.

Flow: Interview completed -> HR opens candidate -> report service reads record -> PDF/CSV/JSON -> download

### Slide 67: Report content should mirror the candidate details panel plus ATS/KYC context.

- Candidate details: name, email, application_id, job_id/job title.
- ATS: final score, status, semantic/skill/education/experience/project scores, matched/missing skills.
- Verification: Aadhaar status, masked Aadhaar, name match score, face/liveness score, timestamps.
- Interview: question source, questions, expected answers, transcripts, audio paths/links, per-rubric Qwen scores, feedback, missing points, final interview score.
- Metadata: submittedAt per answer, completedAt/interview_completed_at, grading model.

| Report section | Data source |
| --- | --- |
| Candidate | application root fields |
| ATS | ats_result + component scores |
| KYC/face | aadhaar_verification + live_face_verification |
| Answers | interview_answers |
| Final score | interview_score |

## Models and Offline/Online Requirements

### Slide 68: Model inventory: language, speech, semantic, face, OCR, and document detection.

- Qwen2.5:7b via Ollama: local LLM for question generation and grading; pull once, then offline if Ollama runs locally.
- faster-whisper medium/small/base: local speech-to-text; first load downloads model files to backend/models/whisper, then offline.
- TechWolf/JobBERT-v3: semantic ATS embeddings through sentence-transformers; first load may download from Hugging Face, then offline cache.
- InsightFace buffalo_l / ArcFace: face embeddings; first model fetch/cache may require internet if not already present, then offline.
- YOLO Indian ID .pt models: bundled under indian-id-validator/models; no first download for those files.
- PaddleOCR/PaddlePaddle: OCR runtime for ID validator; package/model assets may need setup/cache, then offline.
- OpenCV Haar cascade: bundled with OpenCV package; used for resume/Aadhaar face cropping.

### Slide 69: Model offline/online behavior table


| Model/package | Purpose | First internet? | Offline after cache? | Cache/store |
| --- | --- | --- | --- | --- |
| Qwen2.5:7b | LLM generation/grading | Yes: ollama pull | Yes | Ollama model store |
| faster-whisper medium | transcription | Yes first load | Yes | backend/models/whisper |
| JobBERT-v3 | semantic ATS | Yes first load | Yes | HF cache/backend models |
| InsightFace buffalo_l | face embeddings | Maybe first fetch | Yes | InsightFace cache |
| YOLO .pt ID models | ID detection/classification | No bundled | Yes | indian-id-validator/models |
| PaddleOCR | OCR | Maybe setup/cache | Yes | Paddle cache/env |
| OpenCV Haar | face crop | pip/package | Yes | OpenCV package data |

### Slide 70: Model installation and missing-model failure behavior


| Model | Install/pull | CPU/GPU behavior | Missing failure |
| --- | --- | --- | --- |
| Qwen | Install Ollama; ollama pull qwen2.5:7b | local Ollama runtime | health false; grading fails |
| Whisper | pip faster-whisper; first load downloads model | CPU int8 default | transcription failure/fallback |
| JobBERT | pip sentence-transformers; first load model | torch backend CPU/GPU | semantic score 0 |
| InsightFace | pip insightface onnxruntime | CPUExecutionProvider | face-health failed |
| Indian ID YOLO | bundled .pt + ultralytics | CPU/GPU by ultralytics env | validator subprocess error |
| PaddleOCR | id_venv setup | Paddle CPU/GPU build | OCR/extraction failure |

## Required Python Modules

### Slide 71: Backend Python modules are grouped by API, parsing, AI, and computer vision.


| Group | Packages | Used by |
| --- | --- | --- |
| Server/API | fastapi, uvicorn, pydantic, python-multipart | main.py and routes |
| HTTP/env | requests | qwen_service |
| PDF parsing | PyMuPDF/fitz | resume_parser, id_model_service PDF conversion |
| Semantic NLP | sentence-transformers | semantic_match JobBERT |
| Speech | faster-whisper | whisper_service |
| Face/CV | insightface, onnxruntime, opencv-python, numpy | face verification and photo crops |
| ID validator | ultralytics, paddleocr, paddlepaddle, pandas, matplotlib, huggingface_hub | indian-id-validator env |

### Slide 72: Backend dependencies have two internet moments: package install and model download.

- pip install requirements.txt is required for backend packages.
- setup_id_venv.bat installs Indian ID validator packages into a separate environment.
- Some packages only need internet during pip install; ML packages may also download model weights during first runtime use.
- For offline demos, pre-run model health checks and first transcription/semantic/face load before presenting.

| Package/model | Internet during pip? | Internet at runtime? |
| --- | --- | --- |
| FastAPI/Pydantic/PyMuPDF/OpenCV | Yes | No |
| sentence-transformers + JobBERT | Yes | Yes on first model load |
| faster-whisper | Yes | Yes on first model load |
| insightface buffalo_l | Yes | Maybe if model missing |
| PaddleOCR | Yes | Maybe if OCR assets missing |

## Required Frontend Modules

### Slide 73: Frontend runtime uses a small package footprint plus browser APIs.

- package.json dependencies: react, react-dom, vite, @vitejs/plugin-react.
- No React Router package is used; App.jsx handles routing/state manually.
- API calls use browser fetch with hardcoded http://127.0.0.1:8000 base URLs in API modules/pages.
- Camera and microphone rely on browser permissions and secure/browser-supported contexts.
- MediaRecorder support and MIME support are checked before recording.
- CSS files are page-specific plus global.css.

| Frontend dependency/API | Purpose |
| --- | --- |
| React | stateful pages/components |
| Vite | dev server/build |
| fetch | REST API calls |
| getUserMedia | camera/microphone |
| MediaRecorder | voice answer capture |
| canvas | webcam frame capture |

## Setup and Runtime

### Slide 74: Setup: backend, frontend, ID validator, and model runtimes

- Backend: cd D:\novac_3; venv\Scripts\activate; cd backend; uvicorn app.main:app --reload.
- Frontend: cd D:\novac_3\frontend; npm run dev.
- Indian ID validator: run setup_id_venv.bat; defaults use D:\novac_3\id_venv\Scripts\python.exe and indian-id-validator\inference.py.
- Ollama/Qwen: install Ollama, run ollama pull qwen2.5:7b, start Ollama, check /api/interview/qwen-health.
- Face health: check /api/interview/face-health before demo.
- Whisper: first transcription may download selected model into backend/models/whisper.

### Slide 75: Environment variables control model/runtime behavior.


| Env var | Default / use |
| --- | --- |
| QWEN_BASE_URL | http://127.0.0.1:11434 |
| QWEN_MODEL | qwen2.5:7b |
| USE_QWEN | true |
| WHISPER_MODEL | medium |
| WHISPER_MODEL_DIR | backend/models/whisper |
| WHISPER_DEVICE | cpu |
| WHISPER_COMPUTE_TYPE | int8 |
| FACE_VERIFY_THRESHOLD | 0.38 |
| FRONTEND_BASE_URL | http://localhost:5173 |
| INDIAN_ID_PYTHON | D:\novac_3\id_venv\Scripts\python.exe |
| INDIAN_ID_INFERENCE | D:\novac_3\indian-id-validator\inference.py |

### Slide 76: Demo readiness checklist

- Backend FastAPI running on port 8000.
- Frontend Vite running on port 5173 or another localhost port allowed by CORS.
- Ollama running and qwen2.5:7b pulled.
- Face dependencies installed and /face-health returns success true.
- ID validator venv exists and can classify a sample Aadhaar.
- Whisper first model load already warmed up if internet is unavailable during demo.
- At least one job, question bank, and candidate resume are available for the demo flow.

Flow: Backend -> Frontend -> Ollama/Qwen -> ID validator -> Face health -> Whisper cache -> Demo data

## Failure Modes and Debugging

### Slide 77: Failure modes and fixes: AI runtimes


| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Qwen health false | Ollama not running or model missing | Start Ollama; ollama pull qwen2.5:7b |
| Qwen invalid JSON | LLM output not parseable | Retry; repair flow runs; tighten prompt if recurring |
| Grading failed | Qwen unavailable or invalid after repair | Check /qwen-health; retry answer submission |
| Whisper delay | First model download/loading | Prewarm model; set smaller WHISPER_MODEL |
| Semantic score 0 | JobBERT load failed | Check sentence-transformers/cache/internet |

### Slide 78: Failure modes and fixes: browser and workflow


| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Camera permission denied | Browser blocked camera | Allow permission; reload candidate page |
| No face detected | Poor frame/reference image | Center face; improve lighting; ensure Aadhaar/resume photo exists |
| Microphone unavailable | Permission or device issue | Allow microphone; check browser/device |
| No transcript | Empty/unclear audio or Whisper failure | Record again; check backend logs |
| Question bank missing | No {job_id}.json | Upload/create bank or use Qwen generation path |
| Route guard blocks interview | Aadhaar/face flags false | Complete verification first |
| Report download missing | Assumed route/file not generated | Generate report after interview completion |

### Slide 79: Failure modes and fixes: storage and repo hygiene


| Symptom | Cause | Fix |
| --- | --- | --- |
| Large Git changes | model caches/storage committed | Add ignores; remove cached artifacts from Git |
| Missing local folders | storage directories absent | application_store_service creates core folders; create candidate paths as needed |
| Application delete leaves files | path not inside owned roots | Keep artifacts under storage/uploads owned roots |
| Invalid JSON store | manual edit/truncated file | Restore backup or valid []/records |
| ID validator timeout | heavy OCR/model or bad env | Check id_venv, reduce input, inspect stderr |

## Security and Integrity

### Slide 80: Security and integrity controls already present

- Candidate cannot type answers during active interview; transcript is read-only and generated from voice.
- Camera remains visible during interview to discourage impersonation.
- Aadhaar name matching verifies identity before face verification.
- Face + liveness check gates the interview route.
- Interview links include expiry and used flags; completed interviews cannot be restarted.
- Aadhaar numbers are masked before storage in verification fields.

Flow: ATS pass -> Aadhaar check -> Face+liveness -> Voice-only interview -> Qwen graded -> Completed/used link

### Slide 81: Production security hardening still matters.

- Add HR authentication and role-based authorization.
- Replace clipboard/manual link sharing with signed email delivery.
- Encrypt sensitive uploaded documents, audio, and reports at rest.
- Add audit logging for link creation, verification, report download, and deletion.
- Move from local JSON to MongoDB or another production database with indexes and access control.
- Define retention policy for Aadhaar files, live frames, audio, transcripts, and reports.

## Limitations

### Slide 82: Current limitations

- Local JSON storage is demo-friendly but not production-grade for concurrency, indexing, audit, or access control.
- ATS weight calibration needs normalization and validation against real hiring outcomes.
- Qwen JSON output can fail despite strict prompting; repair/regrade helps but does not remove risk.
- Model startup and first-download delays can disrupt demos if caches are not warmed.
- Hardware affects Whisper, JobBERT, InsightFace, and OCR performance.
- Liveness check is assumed implemented in this deck; production anti-spoofing should be independently tested.
- Report download route was not found in current code search and is treated as an assumed capability.

## Roadmap

### Slide 83: Future improvements

- Migrate persistence to MongoDB with indexes, migrations, audit fields, and backups.
- Add HR authentication, role-based access, and signed candidate links.
- Integrate email/SMS delivery for verification/interview links.
- Implement first-class PDF/CSV/JSON report generation endpoints if not already added.
- Add model readiness dashboard for Qwen, Whisper, JobBERT, InsightFace, and ID validator.
- Improve liveness/anti-spoofing with challenge-response and multi-frame scoring.
- Calibrate ATS weights with labeled data and add threshold configuration per role.
- Add automated tests for parsers, ATS math, KYC edge cases, route guards, Qwen parsing, and interview completion.
- Add HR analytics dashboard for pipeline conversion, score distributions, and model health.

Flow: Production DB -> Auth -> Signed links -> Report API -> Model health -> Tests -> Analytics

## Conclusion

### Slide 84: Review conclusion

- NOVAC AI Hiring Platform is a connected local-first hiring workflow with clear boundaries between frontend, API routes, services, storage, and AI models.
- The strongest implemented backbone is the application_id record that accumulates resume, ATS, KYC, face, interview, transcript, grading, and report-ready data.
- The highest-priority engineering work for production is persistence, security, model readiness, report export, liveness validation, ATS calibration, and tests.
- With warmed model caches and running Ollama/FastAPI/Vite, the project is suitable for an end-to-end technical demo.

Flow: Codebase -> Pipelines -> Models -> Storage -> Demo -> Production roadmap
