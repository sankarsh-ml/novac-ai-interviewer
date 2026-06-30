import { useEffect, useState } from "react";
import "../styles/JobApplicationsPage.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function JobApplicationsPage({job,onBack,onViewShortlisted,onViewResume}) {

  const [applications, setApplications] =useState([]);

  const [shortlistCount, setShortlistCount] = useState("");
  useEffect(() => {
    fetchApplications();
  }, []);

  const fetchApplications = async () => {

    try {

      const response =
        await fetch(
          `${API_BASE_URL}/api/hr/jobs/${job.id}/applications`
        );

      const data =
        await response.json();

      if (data.success) {

        const sortedApplications = (data.applications || []).sort((a, b) => (b.ats_score ?? 0) - (a.ats_score ?? 0));
        setApplications(sortedApplications);
      }
      console.log(applications);
    } catch (error) {

      console.error(error);
    }
  };

  const deleteApplication = async (applicationId) => {
    if (!window.confirm("Delete this candidate and local uploaded files?")) {
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/hr/applications/${encodeURIComponent(applicationId)}`,
        {
          method: "DELETE",
        }
      );
      const data = await response.json();

      if (!response.ok || !data.success) {
        alert(data.detail || data.message || "Failed to delete candidate");
        return;
      }

      fetchApplications();
    } catch (error) {
      console.error(error);
      alert("Failed to delete candidate");
    }
  };

  const updateHRDecision = async (applicationId, decision) => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/hr/applications/${applicationId}/hr-decision`,
          {
            method: "PATCH",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              decision,
            }),
          }
        );

        const data = await response.json();

        if (!response.ok || !data.success) {
          alert(data.detail || data.message || "Failed to update HR decision.");
          return;
        }

        fetchApplications();
      } catch (error) {
        console.error(error);
        alert("Failed to update HR decision.");
      }
    };

  return (

  <main className="hr-page">

    <div className="hr-container">

      <button
        className="back-button"
        onClick={onBack}
      >
        Back
      </button>

      <h1>
        {job.title}
      </h1>
      
      <div className="shortlist-toolbar">
      <button
        className="hr-button"
        onClick={() => onViewShortlisted(job)}
      >
        View Shortlisted Candidates
      </button>
      </div>
      
      <div className="job-summary">

        <div className="summary-card">
          <span>Total Applications</span>
          <strong>
            {applications.length}
          </strong>
        </div>

        <div className="summary-card">
          <span>Selected</span>
          <strong>
            {
              applications.filter(
                app =>
                  app.hr_decision === "selected"
              ).length
            }
          </strong>
        </div>

        <div className="summary-card">
          <span>Rejected</span>
          <strong>
            {
              applications.filter(
                app =>
                  app.hr_decision === "rejected"
              ).length
            }
          </strong>
        </div>

      </div>

      <div className="table-wrapper">

        <table className="applications-table">

          <thead>

            <tr>

              <th>Rank</th>

              <th>Candidate</th>

              <th>Email</th>

              <th>ATS</th>

              <th>Semantic</th>

              <th>Skill</th>

              <th>Education</th>

              <th>Experience</th>

              <th>Project</th>

              <th>ATS Status</th>

              <th>HR Decision</th>

              <th>Resume</th>

              <th>Delete</th>

            </tr>

          </thead>

          <tbody>

            {applications.map((app, index) => (
                <tr
                  key={
                    app.application_id
                  }
                >
                  <td>
                    <span className="rank-badge">
                        {index + 1}
                    </span>
                  </td>

                  <td>
                    {
                      app.candidate_name
                    }
                  </td>

                  <td>
                    {
                      app.email || "Not Available"
                    }
                  </td>

                  <td>
                    {
                      app.ats_score ?? "-"
                    }
                  </td>

                  <td>
                    {
                      app.semantic_score ?? "-"
                    }
                  </td>

                  <td>
                    {
                      app.skill_score ?? "-"
                    }
                  </td>

                  <td>
                    {
                      app.education_score ?? "-"
                    }
                  </td>

                  <td>
                    {
                      app.experience_score ?? "-"
                    }
                  </td>

                  <td>
                    {
                      app.project_score ?? "-"
                    }
                  </td>

                  <td>

                    <span
                      className={`status-badge ${getAtsStatusClass(app.ats_status)}`}
                    >
                      {
                        formatStatus(app.ats_status || "processing")
                      }
                    </span>

                  </td>
                  
                  <td>

                    <span
                      className={`status-badge ${
                        app.hr_decision === "selected"
                          ? "status-pass"
                          : app.hr_decision === "rejected"
                          ? "status-fail"
                          : "status-processing"
                      }`}
                    >
                      {formatStatus(app.hr_decision || "pending")}
                    </span>

                    <div
                      style={{
                        display: "flex",
                        gap: "6px",
                        marginTop: "8px",
                        justifyContent: "center",
                      }}
                    >
                      <button
                        className="hr-button"
                        onClick={() =>
                          updateHRDecision(
                            app.application_id,
                            "selected"
                          )
                        }
                      >
                        Select
                      </button>

                      <button
                        className="delete-button"
                        onClick={() =>
                          updateHRDecision(
                            app.application_id,
                            "rejected"
                          )
                        }
                      >
                        Reject
                      </button>

                    </div>

                  </td>
                  <td>
                    <div className="resume-actions">
                      <button
                        className="resume-button download"
                        onClick={() =>
                          window.open(
                            `${API_BASE_URL}/api/hr/applications/${app.application_id}/resume/download`,
                            "_blank"
                          )
                        }
                      >
                        📄 Resume
                      </button>
                      <button
                          className="resume-button view"
                          onClick={() => onViewResume(app)}
                      >
                          View Resume
                      </button>
                    </div>
                  </td>

                  <td>
                    <button
                      className="delete-button"
                      type="button"
                      onClick={() =>
                        deleteApplication(
                          app.application_id
                        )
                      }
                    >
                      Delete
                    </button>
                  </td>

                </tr>

              )
            )}

          </tbody>

        </table>

      </div>
    </div>

  </main>

);
}

export default JobApplicationsPage;


function CandidateDetailsPanel({ application, onClose }) {
  const answers = Object.values(application.interview_answers || {}).filter(
    (answer) => answer && typeof answer === "object"
  );
  const questionSource = application.question_source || application.interview_questions?.source || "";

  return (
    <section className="candidate-details-panel">
      <div className="candidate-details-header">
        <div>
          <p className="details-eyebrow">Candidate Details</p>
          <h2>{application.candidate_name || "Candidate"}</h2>
          <p>{application.email || "No email available"}</p>
        </div>
        <button className="link-button" type="button" onClick={onClose}>
          Close
        </button>
      </div>

      <div className="details-grid">
        <DetailItem label="ATS Score" value={formatScore(application.ats_score)} />
        <DetailItem label="Interview Score" value={formatScore(application.interview_score ?? application.interviewScore)} />
        <DetailItem label="Question Source" value={formatQuestionSource(questionSource)} />
        <DetailItem label="Interview Status" value={getInterviewLabel(application)} />
      </div>

      <div className="answer-review-list">
        {answers.length ? (
          answers.map((answer, index) => (
            <article className="answer-review-card" key={answer.questionId || answer.question_id || index}>
              <div className="answer-review-heading">
                <span>Question {index + 1}</span>
                <strong>{formatScoreWithMax(getAnswerScore(answer, "finalScore"))}</strong>
              </div>
              <p className="review-question">{answer.question}</p>
              {formatQuestionSource(questionSource) === "Question Bank" && answer.expectedAnswer && (
                <ReviewBlock label="Expected Answer" value={answer.expectedAnswer} />
              )}
              <ReviewBlock label="Candidate Transcript" value={answer.transcript || answer.answerText || answer.answer_text} />
              <ReviewBlock label="Audio Path" value={answer.audioPath || answer.audio_path || "Not available"} />
              <div className="details-grid compact">
                <DetailItem label="Relevance" value={formatScore(getAnswerScore(answer, "relevance"))} />
                <DetailItem label="Technical" value={formatScore(getAnswerScore(answer, "technical"))} />
                <DetailItem label="Depth" value={formatScore(getAnswerScore(answer, "depth"))} />
                <DetailItem label="Clarity" value={formatScore(getAnswerScore(answer, "clarity"))} />
              </div>
              <ReviewBlock label="Feedback" value={answer.feedback || answer.grading?.feedback || answer.evaluation?.feedback || "Not available"} />
              <ReviewBlock
                label="Missing Points"
                value={formatList(answer.missingPoints || answer.missing_points || answer.grading?.missingPoints || answer.grading?.missing_points || answer.evaluation?.missingPoints || answer.evaluation?.missing_points)}
              />
              <ReviewBlock label="Submitted At" value={answer.submittedAt || answer.submitted_at || "Not available"} />
            </article>
          ))
        ) : (
          <p className="empty-details">No interview answers submitted yet.</p>
        )}
      </div>
    </section>
  );
}


function DetailItem({ label, value }) {
  return (
    <article className="detail-item">
      <span>{label}</span>
      <strong>{value ?? "Not Available"}</strong>
    </article>
  );
}


function ReviewBlock({ label, value }) {
  return (
    <div className="review-block">
      <span>{label}</span>
      <p>{value || "Not available"}</p>
    </div>
  );
}


function formatQuestionSource(value) {
  const normalized = String(value || "").toLowerCase();

  if (normalized === "question_bank") {
    return "Question Bank";
  }

  if (normalized === "qwen") {
    return "Qwen";
  }

  return "Not Started";
}


function getAnswerScore(answer, field) {
  const aliases = {
    finalScore: ["finalScore", "final_score", "score"],
    relevance: ["relevance", "relevanceScore", "relevance_score"],
    technical: ["technical", "technicalScore", "technical_score", "technicalAccuracy", "technical_accuracy"],
    depth: ["depth", "depthScore", "depth_score"],
    clarity: ["clarity", "clarityScore", "clarity_score"],
  };
  const keys = aliases[field] || [field];
  const sources = [answer, answer?.grading, answer?.evaluation];

  for (const source of sources) {
    if (!source || typeof source !== "object") {
      continue;
    }

    for (const key of keys) {
      const score = getScoreValue(source[key]);

      if (score !== null) {
        return score;
      }
    }
  }

  return null;
}


function formatScore(value) {
  const score = getScoreValue(value);
  return score === null ? "Not graded" : score.toFixed(1);
}


function formatScoreWithMax(value) {
  const score = getScoreValue(value);
  return score === null ? "Not graded" : `${score.toFixed(1)}/10`;
}


function getScoreValue(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  if (typeof value === "boolean") {
    return null;
  }

  if (typeof value === "number") {
    return Number.isFinite(value) ? Math.max(0, Math.min(10, value)) : null;
  }

  const match = String(value).match(/-?\d+(?:\.\d+)?/);

  if (!match) {
    return null;
  }

  const number = Number(match[0]);

  if (!Number.isFinite(number)) {
    return null;
  }

  return Math.max(0, Math.min(10, number));
}


function formatList(value) {
  if (Array.isArray(value)) {
    return value.length ? value.join(", ") : "None";
  }

  return value || "None";
}


function formatStatus(value) {
  return String(value || "Not Started")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}


function getAtsStatusClass(status) {
  const normalized = String(status || "").toLowerCase();

  if (normalized === "passed") {
    return "status-pass";
  }

  if (normalized === "failed") {
    return "status-fail";
  }

  return "status-processing";
}


function getVerificationLabel(application) {
  if (
    application.verification_completed === true ||
    application.faceVerified === true ||
    application.face_verified === true ||
    String(application.verification_status || "").toLowerCase() === "verified"
  ) {
    return "Verified";
  }

  return "Not Verified";
}


function getVerificationStatusClass(application) {
  return getVerificationLabel(application) === "Verified" ? "status-pass" : "status-muted";
}


function getInterviewLabel(application) {
  const status = String(application.interview_status || application.interviewStatus || "").toLowerCase();

  if (application.interview_completed === true || status === "completed") {
    return "Interview Completed";
  }

  if (status === "in_progress") {
    return "In Progress";
  }

  if (status === "partial") {
    return "Partial";
  }

  if (status === "quit") {
    return "Quit";
  }

  if (status === "expired") {
    return "Expired";
  }

  if (isScheduleExpired(application)) {
    return "Expired";
  }

  return "Not Started";
}


function getInterviewStatusClass(application) {
  const label = getInterviewLabel(application);

  if (label === "Interview Completed") {
    return "status-pass";
  }

  if (label === "In Progress") {
    return "status-processing";
  }

  if (["Partial", "Quit", "Expired"].includes(label)) {
    return "status-fail";
  }

  return "status-muted";
}


function isScheduleExpired(application) {
  const scheduledAt = new Date(application?.interview_scheduled_at || "");

  if (!Number.isFinite(scheduledAt.getTime())) {
    return false;
  }

  return Date.now() > scheduledAt.getTime() + 60 * 60 * 1000;
}
