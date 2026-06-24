import { useEffect, useState } from "react";

import {
  acceptApplication,
  clearOldRecords,
  deleteInterviewCandidate,
  fetchInterviewCandidates,
  scoreResume,
  uploadResume,
} from "../api/resumeApi.js";
import "../styles/HRDashboardPage.css";


function HRDashboardPage() {
  const [jobs, setJobs] = useState([]);
  const [visibleApplications, setVisibleApplications] = useState([]);
  const [resumeFile, setResumeFile] = useState(null);
  const [selectedJob, setSelectedJob] = useState("");
  const [currentApplication, setCurrentApplication] = useState(null);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [inviteLink, setInviteLink] = useState("");
  const [copyStatus, setCopyStatus] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [uploadStatus, setUploadStatus] = useState("");
  const [isUploadingResume, setIsUploadingResume] = useState(false);
  const [isAcceptingResume, setIsAcceptingResume] = useState(false);
  const [isClearingRecords, setIsClearingRecords] = useState(false);

  useEffect(() => {
    fetchJobs();
    loadDashboardRecords();
  }, []);

  const fetchJobs = async () => {
    try {
      const response = await fetch("http://127.0.0.1:8000/api/hr/jobs");
      const data = await response.json();

      if (data.success) {
        setJobs(data.jobs);
      }
    } catch (error) {
      console.error("Error fetching jobs:", error);
    }
  };

  const loadDashboardRecords = async () => {
    try {
      const applications = await fetchInterviewCandidates();
      setVisibleApplications(filterVisibleApplications(applications));
    } catch (error) {
      console.error("Error fetching interview candidates:", error);
    }
  };

  const handleResumeFileChange = (event) => {
    const selectedFile = event.target.files?.[0] || null;
    setUploadError("");
    setUploadStatus("");
    setCopyStatus("");

    if (!selectedFile) {
      setResumeFile(null);
      return;
    }

    if (!selectedFile.name.toLowerCase().endsWith(".pdf")) {
      setResumeFile(null);
      setUploadError("Please choose a PDF resume.");
      return;
    }

    setResumeFile(selectedFile);
  };

  const handleResumeUpload = async () => {
    if (!selectedJob) {
      setUploadError("Please select a job before uploading a resume.");
      return;
    }

    if (!resumeFile) {
      setUploadError("Please select a PDF resume.");
      return;
    }

    try {
      setIsUploadingResume(true);
      setUploadError("");
      setCopyStatus("");
      setInviteLink("");
      setCurrentApplication(null);
      setUploadStatus("Uploading resume...");

      const uploadResponse = await uploadResume(resumeFile, selectedJob);
      const applicationId = uploadResponse.data?.application_id;

      if (!applicationId) {
        throw new Error("Backend did not return application_id for the uploaded resume.");
      }

      setUploadStatus("Running ATS screening...");
      const atsResponse = await scoreResume(applicationId);
      const atsResult = atsResponse.result || atsResponse;
      const atsScore = getAtsScore(atsResponse) ?? getAtsScore(atsResult) ?? 0;

      setCurrentApplication({
        application_id: applicationId,
        candidate_name: atsResponse.candidate_name || uploadResponse.data?.resume_name || "Candidate",
        file_name: uploadResponse.data?.file_name || resumeFile.name,
        ats_score: atsScore,
        ats_status: atsScore >= 65 ? "passed" : "failed",
        matched_skills: atsResponse.matched_skills || atsResult.matched_skills || [],
        missing_skills: atsResponse.missing_skills || atsResult.missing_skills || [],
      });
      setResumeFile(null);
      setUploadStatus("Resume uploaded and ATS score generated.");
      await loadDashboardRecords();
    } catch (error) {
      setUploadError(error.message || "Could not upload and score resume.");
    } finally {
      setIsUploadingResume(false);
    }
  };

  const handleAcceptResume = async () => {
    const applicationId = currentApplication?.application_id;

    if (!applicationId) {
      setUploadError("No scored application is available to accept.");
      return;
    }

    try {
      setIsAcceptingResume(true);
      setUploadError("");
      setCopyStatus("");
      const response = await acceptApplication(applicationId);
      setInviteLink(response.invite_link);
      setCurrentApplication((application) => ({
        ...application,
        status: "accepted",
        invite_link: response.invite_link,
        invite_token: response.invite_token,
      }));
      await loadDashboardRecords();
    } catch (error) {
      setUploadError(error.message || "Could not accept resume.");
    } finally {
      setIsAcceptingResume(false);
    }
  };

  const handleCopyLink = async (link) => {
    if (!link) {
      return;
    }

    try {
      await navigator.clipboard.writeText(link);
      setCopyStatus("Copied.");
    } catch (error) {
      window.prompt("Copy candidate link", link);
      setCopyStatus("Copy manually from the prompt.");
    }
  };

  const handleClearOldRecords = async () => {
    try {
      setIsClearingRecords(true);
      setUploadError("");
      setUploadStatus("Clearing old local JSON records...");
      await clearOldRecords();
      setVisibleApplications([]);
      setCurrentApplication(null);
      setSelectedCandidate(null);
      setInviteLink("");
      setUploadStatus("Old records cleared.");
      await loadDashboardRecords();
    } catch (error) {
      setUploadError(error.message || "Could not clear old records.");
    } finally {
      setIsClearingRecords(false);
    }
  };

  const handleDeleteCandidate = async (application) => {
    const candidateName = application.candidate_name || application.resume?.candidate_name || "this candidate";

    if (!window.confirm(`Delete ${candidateName}'s candidate record and all related local files?`)) {
      return;
    }

    try {
      await deleteInterviewCandidate(application.application_id);

      if (selectedCandidate?.application_id === application.application_id) {
        setSelectedCandidate(null);
      }

      await loadDashboardRecords();
    } catch (error) {
      setUploadError(error.message || "Could not delete candidate record.");
    }
  };

  return (
    <main className="hr-page">
      <div className="hr-container">
        <div className="hr-header">
          <p className="eyebrow">HR Dashboard</p>
          <h1>AI Hiring Platform</h1>
          <button
            className="hr-secondary-button"
            type="button"
            onClick={handleClearOldRecords}
            disabled={isClearingRecords}
          >
            {isClearingRecords ? "Clearing..." : "Clear Old Records"}
          </button>
        </div>

        <section className="hr-panel">
          <h2>Upload Resume</h2>

          <select
            className="hr-input"
            value={selectedJob}
            onChange={(event) => setSelectedJob(event.target.value)}
          >
            <option value="">Select job</option>
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.title}
              </option>
            ))}
          </select>

          <label className="hr-file-label" htmlFor="hr-resume-file">
            <span>{resumeFile ? resumeFile.name : "Select PDF resume"}</span>
            <input id="hr-resume-file" type="file" accept=".pdf,application/pdf" onChange={handleResumeFileChange} />
          </label>

          <button className="hr-button" type="button" onClick={handleResumeUpload} disabled={isUploadingResume}>
            {isUploadingResume ? "Processing..." : "Upload Resume and Run ATS"}
          </button>

          {uploadStatus && !currentApplication && <p className="success-message">{uploadStatus}</p>}
          {uploadError && <p className="error-message">{uploadError}</p>}

          {currentApplication && (
            <AtsResultCard
              application={currentApplication}
              statusMessage={uploadStatus}
              inviteLink={inviteLink || currentApplication.invite_link}
              accepting={isAcceptingResume}
              copyStatus={copyStatus}
              onAccept={handleAcceptResume}
              onCopy={handleCopyLink}
            />
          )}
        </section>

        <section className="applications-section">
          <div className="section-heading-row">
            <h2>Accepted Candidates</h2>
            <button className="hr-secondary-button" type="button" onClick={loadDashboardRecords}>
              Refresh
            </button>
          </div>

          <div className="applications-list">
            {visibleApplications.length === 0 ? (
              <p>No accepted candidates yet.</p>
            ) : (
              visibleApplications.map((application) => (
                <ApplicationCard
                  key={application.application_id}
                  application={application}
                  onCopy={handleCopyLink}
                  onViewResults={setSelectedCandidate}
                  onDelete={handleDeleteCandidate}
                />
              ))
            )}
          </div>
        </section>

        {selectedCandidate && (
          <CandidateResultsPanel
            application={selectedCandidate}
            onClose={() => setSelectedCandidate(null)}
          />
        )}
      </div>
    </main>
  );
}


function AtsResultCard({ application, statusMessage, inviteLink, accepting, copyStatus, onAccept, onCopy }) {
  const atsScore = getAtsScore(application);
  const hasAtsScore = atsScore !== null;
  const atsPassed = hasAtsScore && atsScore >= 65;

  return (
    <article className="application-card active-application-card">
      <header className="application-card-header">
        <div>
          <h3>{application.candidate_name || "Candidate"}</h3>
          <p>Resume: {application.file_name || "Not available"}</p>
          <p>Application ID: {application.application_id}</p>
        </div>
        <div className="total-score-box">
          <span>ATS score</span>
          <strong>{hasAtsScore ? `${atsScore}%` : "Not generated"}</strong>
          <small>{hasAtsScore ? (atsPassed ? "passed" : "failed") : "pending"}</small>
        </div>
      </header>

      {statusMessage && <p className="success-message upload-result-message">{statusMessage}</p>}

      <div className="application-actions">
        {atsPassed ? (
          <button
            className="hr-button compact"
            type="button"
            onClick={onAccept}
            disabled={accepting || Boolean(inviteLink)}
          >
            {accepting ? "Accepting..." : inviteLink ? "Accepted" : "Accept Resume"}
          </button>
        ) : (
          <button className="hr-button compact rejected" type="button" disabled>
            Rejected / ATS Failed
          </button>
        )}
        {inviteLink && (
          <button className="hr-secondary-button" type="button" onClick={() => onCopy(inviteLink)}>
            Copy Link
          </button>
        )}
      </div>

      {inviteLink && (
        <>
          <p className="invite-label">Candidate link:</p>
          <p className="invite-link-line">{inviteLink}</p>
          {copyStatus && <p className="success-message">{copyStatus}</p>}
        </>
      )}
    </article>
  );
}


function ApplicationCard({ application, onCopy, onViewResults, onDelete }) {
  const session = application.interview_session || {};
  const questions = getCandidateQuestions(application);
  const submittedCount = questions.filter(hasSubmittedAnswer).length;
  const finalScore = application.total_score ?? session.total_score ?? 0;
  const maxScore = application.max_score ?? session.max_score ?? 50;
  const inviteLink = application.invite_link || "";
  const atsScore = getAtsScore(application);
  const hasAtsScore = atsScore !== null;
  const interviewStatus = getInterviewStatus(application);
  const canViewResults = submittedCount > 0 || interviewStatus === "completed" || interviewStatus === "abandoned" || interviewStatus === "incomplete";
  const interviewCompleted = interviewStatus === "completed";
  const canCopyLink = Boolean(inviteLink) && !["completed", "interview_completed"].includes(String(application.status || "")) && interviewStatus !== "completed";

  return (
    <article className="application-card">
      <header className="application-card-header">
        <div>
          <h3>{application.candidate_name || application.resume?.candidate_name || "Candidate"}</h3>
          <p>Resume: {application.resume_file || application.file_name || "Not available"}</p>
          <p>Status: {getCandidateStatus(application)}</p>
          <p>Interview: {interviewStatus}</p>
        </div>
        <div className="total-score-box">
          <span>ATS score</span>
          <strong>{hasAtsScore ? `${atsScore}%` : "Not generated"}</strong>
          <small>{hasAtsScore ? (atsScore >= 65 ? "passed" : "failed") : "pending"}</small>
        </div>
      </header>

      <div className="application-meta-grid">
        <ResultItem label="Candidate status" value={getCandidateStatus(application)} />
        <ResultItem label="Interview score" value={interviewCompleted ? `${finalScore}/${maxScore}` : "Not completed"} />
        <ResultItem label="Aadhaar" value={application.aadhaar_verified ? "Verified" : "Pending"} />
        <ResultItem label="Face" value={application.face_verified || session.face_verified ? "Verified" : "Pending"} />
      </div>

      <div className="application-actions">
        {canCopyLink && (
          <button className="hr-secondary-button" type="button" onClick={() => onCopy(inviteLink)}>
            Copy Link
          </button>
        )}
        {canViewResults && (
          <button className="hr-secondary-button" type="button" onClick={() => onViewResults(application)}>
            View Results
          </button>
        )}
        <button className="hr-danger-button" type="button" onClick={() => onDelete(application)}>
          Delete
        </button>
      </div>
    </article>
  );
}


function CandidateResultsPanel({ application, onClose }) {
  const session = application.interview_session || {};
  const questions = getCandidateQuestions(application);
  const atsScore = getAtsScore(application);
  const totalScore = application.total_score ?? session.total_score ?? 0;
  const maxScore = application.max_score ?? session.max_score ?? 50;
  const interviewStatus = getInterviewStatus(application);

  return (
    <section className="result-detail-panel">
      <button className="hr-secondary-button" type="button" onClick={onClose}>
        Back to candidates
      </button>

      <header className="result-card-header">
        <div>
          <h2>{application.candidate_name || application.resume?.candidate_name || "Candidate"}</h2>
          <p>Resume: {application.resume_file || application.file_name || "Not available"}</p>
          <p>ATS score: {atsScore === null ? "Not generated" : `${atsScore}%`}</p>
          <p>Aadhaar: {application.aadhaar_verified ? "Verified" : "Pending"}</p>
          <p>Face: {application.face_verified || session.face_verified ? "Verified" : "Pending"}</p>
          <p>Interview: {interviewStatus}</p>
        </div>
        <div className="total-score-box">
          <span>Total score</span>
          <strong>{totalScore}/{maxScore}</strong>
          <small>{interviewStatus}</small>
        </div>
      </header>

      <div className="result-question-list">
        {questions.map((question, index) => (
          <section className="result-question" key={question.question_id || index}>
            <div className="result-question-topline">
              <span>Q{index + 1}</span>
              {question.difficulty && <b>{question.difficulty}</b>}
              <strong>{question.score ?? 0}/10</strong>
            </div>
            <p className="result-question-text">{question.question_text}</p>
            <p><strong>Transcript:</strong> {getQuestionTranscript(question)}</p>
            <p><strong>Feedback:</strong> {getQuestionFeedback(question)}</p>
          </section>
        ))}
      </div>
    </section>
  );
}


function ResultItem({ label, value }) {
  return (
    <article className="application-meta-item">
      <span>{label}</span>
      <strong>{value ?? "Not available"}</strong>
    </article>
  );
}


function filterVisibleApplications(applications) {
  const visibleById = new Map();

  for (const application of applications) {
    const status = String(application.status || "").toLowerCase();
    const candidateStatus = String(application.candidate_status || "").toLowerCase();
    const hasMeaningfulStatus = [
      "accepted",
      "invited",
      "interview_completed",
      "completed",
    ].includes(status) || [
      "invited",
      "aadhaar_verified",
      "face_verified",
      "interview_in_progress",
      "completed",
    ].includes(candidateStatus);
    const hasInvite = Boolean(application.invite_link || application.invite_token);
    const hasAtsScore = getAtsScore(application) !== null;

    if ((!hasInvite && !hasMeaningfulStatus) || (!hasAtsScore && !hasInvite)) {
      continue;
    }

    visibleById.set(application.application_id || application._id, application);
  }

  return [...visibleById.values()]
    .sort((first, second) => (
      new Date(candidateSortDate(second)) -
      new Date(candidateSortDate(first))
    ));
}


function getAtsScore(application) {
  const candidates = [
    application?.ats_score,
    application?.ats_result?.ats_score,
    application?.score,
    application?.atsScore,
    application?.match_score,
    application?.percentage,
  ];

  for (const value of candidates) {
    if (value === null || value === undefined || value === "") {
      continue;
    }

    const score = Number(value);

    if (Number.isFinite(score)) {
      return Number.isInteger(score) ? score : Number(score.toFixed(2));
    }
  }

  return null;
}


function getCandidateStatus(application) {
  if (application.candidate_status) {
    return application.candidate_status;
  }

  if (application.interview_status === "completed") {
    return "completed";
  }

  if (application.interview_status === "in_progress") {
    return "interview_in_progress";
  }

  if (application.face_verified || application.interview_session?.face_verified) {
    return "face_verified";
  }

  if (application.aadhaar_verified) {
    return "aadhaar_verified";
  }

  if (application.invite_token) {
    return "invited";
  }

  return application.status || application.ats_status || "pending";
}


function getInterviewStatus(application) {
  return (
    application.interview_status ||
    application.interview_session?.status ||
    "not_started"
  );
}


function getCandidateQuestions(application) {
  if (Array.isArray(application.questions)) {
    return application.questions;
  }

  if (Array.isArray(application.interview_session?.questions)) {
    return application.interview_session.questions;
  }

  return [];
}


function candidateSortDate(application) {
  return (
    application.accepted_at ||
    application.created_at ||
    application.interview_session?.completed_at ||
    application.updated_at ||
    0
  );
}


function hasSubmittedAnswer(question) {
  return Boolean(
    question?.submitted_at ||
    question?.transcript ||
    question?.score !== null && question?.score !== undefined
  );
}


function getQuestionTranscript(question) {
  const transcript = String(question?.transcript || "").trim();
  return transcript || "Not answered";
}


function getQuestionFeedback(question) {
  const feedback =
    question?.feedback ||
    question?.evaluation?.feedback ||
    question?.evaluation?.overall_feedback ||
    question?.evaluation?.technical_feedback ||
    question?.evaluation?.communication_feedback ||
    question?.evaluation?.relevance_feedback;

  if (feedback) {
    return feedback;
  }

  if (hasSubmittedAnswer(question)) {
    return "Answer submitted and evaluated, but detailed feedback was not generated.";
  }

  return "No answer submitted";
}


export default HRDashboardPage;
