import { useEffect, useState } from "react";
import { fetchCandidates } from "@application/useCases/candidateUseCases.js";
import { fetchBulkReports, fetchReport } from "@application/useCases/reportUseCases.js";
import { useDependencies } from "@presentation/hooks/useDependencies.js";
import { downloadBlob, openBlob } from "@shared/utils/fileUtils.js";
import { safeFilename } from "@shared/utils/formatters.js";
import "@presentation/styles/ShortlistedCandidatesPage.css";

function ShortlistedCandidatesPage({job,onBack,onConfigureInterview}) {
  const { candidateRepository, reportRepository } = useDependencies();

  const [applications, setApplications] =
    useState([]);

  const [selectedApplication, setSelectedApplication] =
    useState(null);
  const [reportError, setReportError] = useState("");
  const [viewReportLoadingId, setViewReportLoadingId] = useState("");
  const [reportLoadingId, setReportLoadingId] = useState("");
  const [bulkReportLoading, setBulkReportLoading] = useState(false);
  const [copiedLinkId, setCopiedLinkId] = useState("");

  useEffect(() => {
    fetchApplications();
  }, []);

  const fetchApplications = async () => {

    try {
      const data = await fetchCandidates(candidateRepository, job.id);

      if (data.success) {

          const shortlistedCandidates = (data.applications || [])
          .filter(app => app.hr_decision === "selected")
          .sort((a, b) => (b.ats_score ?? 0) - (a.ats_score ?? 0));

        setApplications(shortlistedCandidates);

      }

    } catch (error) {

      console.error(error);
    }
  };

  const completedApplications = applications.filter(isReportReady);

  const rescheduleInterview = (application) => {
    const applicationId = application?.application_id;

    if (!applicationId) {
      setReportError("Candidate ID is missing.");
      return;
    }

    if (!canRescheduleInterview(application)) {
      setReportError("Completed interviews cannot be rescheduled.");
      return;
    }

    setReportError("");
    onConfigureInterview?.(application, { mode: "reschedule" });
  };

  const copyInterviewLink = async (application) => {
    const link = getInterviewLink(application);

    if (!link) {
      setReportError("No generated interview link is available for this candidate.");
      return;
    }

    setReportError("");

    try {
      await navigator.clipboard.writeText(link);
      setCopiedLinkId(application.application_id);
      window.setTimeout(() => setCopiedLinkId(""), 1800);
    } catch (error) {
      console.error(error);
      setReportError("Could not copy interview link. Please copy it from the candidate record.");
    }
  };

  const viewCandidateReport = async (application) => {
    const applicationId = application?.application_id;

    if (!applicationId) {
      setReportError("Candidate ID is missing.");
      return;
    }

    setReportError("");
    setViewReportLoadingId(applicationId);
    const reportWindow = window.open("", "_blank");

    if (!reportWindow) {
      setViewReportLoadingId("");
      setReportError("Could not open report. Please allow pop-ups for this site.");
      return;
    }

    try {
      const { blob } = await fetchReport(reportRepository, applicationId);
      openBlob(blob, reportWindow);
    } catch (error) {
      console.error(error);
      reportWindow.close();
      setReportError(error.message || "Report generation failed.");
    } finally {
      setViewReportLoadingId("");
    }
  };

  const downloadCandidateReport = async (application) => {
    const applicationId = application?.application_id;

    if (!applicationId) {
      setReportError("Candidate ID is missing.");
      return;
    }

    setReportError("");
    setReportLoadingId(applicationId);

    try {
      const { blob, filename } = await fetchReport(reportRepository, applicationId);
      downloadBlob(blob, filename || `candidate_report_${safeFilename(application.candidate_name || "candidate")}.pdf`);
    } catch (error) {
      console.error(error);
      setReportError(error.message || "Report generation failed.");
    } finally {
      setReportLoadingId("");
    }
  };

  const downloadCompletedReports = async () => {
    if (!completedApplications.length) {
      setReportError("No complete or partial candidate evaluations are available for report generation.");
      return;
    }

    setReportError("");
    setBulkReportLoading(true);

    try {
      const { blob, filename } = await fetchBulkReports(
        reportRepository,
        job.id,
        completedApplications.map((application) => application.application_id).filter(Boolean)
      );
      downloadBlob(blob, filename || "novac_group_candidate_report.pdf");
    } catch (error) {
      console.error(error);
      setReportError(error.message || "Report generation failed.");
    } finally {
      setBulkReportLoading(false);
    }
  };

  return (

    <main className="shortlisted-page">

      <div className="shortlisted-container">

        <button
          className="back-button"
          onClick={onBack}
        >
          Back
        </button>

        <div className="shortlisted-header">

          <h1>
            Shortlisted Candidates
          </h1>

          <p>
            {job.title}
          </p>

        </div>

        <div className="summary-card">

          <span>
            Total Shortlisted
          </span>

          <strong>
            {applications.length}
          </strong>

        </div>

        <div className="report-toolbar">
          <div>
            <span>Available Reports</span>
            <strong>{completedApplications.length}</strong>
          </div>
          <div className="report-toolbar-actions">
            <button
              className="report-button"
              type="button"
              onClick={downloadCompletedReports}
              disabled={!completedApplications.length || bulkReportLoading}
            >
              {bulkReportLoading ? "Generating report..." : "Download All Reports"}
            </button>
          </div>
        </div>

        {reportError && <p className="report-error">{reportError}</p>}

        <div className="table-wrapper">

          <table
            className="shortlisted-table"
          >

            <thead>

              <tr>

                <th>Rank</th>

                <th>
                  Candidate
                </th>

                <th>
                  Email
                </th>

                <th>
                  ATS Score
                </th>

                <th>
                  Interview Status
                </th>

                <th>
                  Interview Link
                </th>

                <th>
                  Report
                </th>

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
                        app.email ||
                        "Not Available"
                      }
                    </td>

                    <td>
                      {
                        app.ats_score
                      }
                    </td>

                    <td>
                      <span className={`status-badge ${getInterviewStatusClass(app)}`}>
                        {getInterviewLabel(app)}
                      </span>
                    </td>

                    <td>

                      <div className="action-group">
                      {isLinkGenerated(app) ? (
                        <button
                          className="send-button copy"
                          type="button"
                          onClick={() => copyInterviewLink(app)}
                        >
                          {copiedLinkId === app.application_id ? "Copied" : "Copy Link"}
                        </button>
                      ) : (
                        <button
                          className="send-button"
                          type="button"
                          onClick={() => onConfigureInterview?.(app)}
                        >
                          Generate Link
                        </button>
                      )}
                        {canRescheduleInterview(app) && (
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() => rescheduleInterview(app)}
                          >
                            Reschedule
                          </button>
                        )}
                        {isLinkGenerated(app) && getNormalizedInterviewStatus(app) === "complete" && (
                          <span className="completed-note">Interview completed - rescheduling unavailable</span>
                        )}
                      </div>

                    </td>

                    <td>
                      <div className="action-group">
                        <button
                          className="link-button"
                          type="button"
                          onClick={() => viewCandidateReport(app)}
                          disabled={!isReportReady(app) || viewReportLoadingId === app.application_id}
                        >
                          {viewReportLoadingId === app.application_id ? "Opening report..." : "View Report"}
                        </button>
                        <button
                          className="report-button compact"
                          type="button"
                          onClick={() => downloadCandidateReport(app)}
                          disabled={!isReportReady(app) || reportLoadingId === app.application_id}
                        >
                          {reportLoadingId === app.application_id ? "Generating report..." : "Download Report"}
                        </button>
                      </div>
                    </td>

                  </tr>

                )
              )}

            </tbody>

          </table>

        </div>

        {selectedApplication && (
          <CandidateDetailsPanel
            application={selectedApplication}
            onClose={() => setSelectedApplication(null)}
          />
        )}

      </div>

    </main>

  );
}

export default ShortlistedCandidatesPage;


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


function isInterviewComplete(application) {
  return (
    application.interview_completed === true ||
    ["complete", "completed"].includes(String(application.interview_status || "").toLowerCase())
  );
}


function isReportReady(application) {
  const status = String(application?.interview_status || application?.interviewStatus || "").toLowerCase();

  return (
    application?.report_available === true ||
    application?.has_report === true ||
    application?.interview_completed === true ||
    application?.interviewCompleted === true ||
    ["complete", "completed", "partial"].includes(status)
  );
}


function getInterviewLink(application) {
  return (
    application?.interviewLink ||
    application?.interview_link ||
    application?.verification_link ||
    application?.link ||
    ""
  );
}


function isLinkGenerated(application) {
  return Boolean(application?.interview_link_generated || getInterviewLink(application));
}


function getInterviewLabel(application) {
  const status = getNormalizedInterviewStatus(application);

  if (status === "complete") {
    return "Complete";
  }

  if (status === "partial") {
    return "Partial";
  }

  return "Not Started";
}


function getNormalizedInterviewStatus(application) {
  const status = String(
    application?.interview_status ||
    application?.interviewStatus ||
    application?.status ||
    application?.latestInterviewStatus ||
    ""
  ).toLowerCase();
  const answeredCount = Number(
    application?.answered_count ??
    application?.answeredCount ??
    application?.answersCount ??
    application?.completedQuestions ??
    0
  ) || 0;
  const totalQuestions = getTotalQuestionCount(application);

  if (
    application?.interview_completed === true ||
    application?.interviewCompleted === true ||
    application?.completedAt ||
    application?.completed_at ||
    application?.interview_completed_at ||
    ["complete", "completed"].includes(status) ||
    (totalQuestions > 0 && answeredCount >= totalQuestions)
  ) {
    return "complete";
  }

  if (
    ["partial", "abandoned", "quit", "quit_midway", "interrupted", "in_progress"].includes(status) ||
    application?.interview_quit_at ||
    (answeredCount > 0 && (!totalQuestions || answeredCount < totalQuestions))
  ) {
    return "partial";
  }

  return "not_started";
}


function canRescheduleInterview(application) {
  if (typeof application?.canReschedule === "boolean") {
    return application.canReschedule;
  }

  return getNormalizedInterviewStatus(application) !== "complete";
}


function getTotalQuestionCount(application) {
  const finalQuestions = application?.finalQuestions || application?.final_questions;

  if (Array.isArray(finalQuestions)) {
    return finalQuestions.length;
  }

  const configuredQuestions = application?.interview_questions?.questions;

  if (Array.isArray(configuredQuestions)) {
    return configuredQuestions.length;
  }

  return Number(
    application?.total_questions ??
    application?.totalQuestions ??
    application?.questionCount ??
    application?.question_count ??
    0
  ) || 0;
}


function getInterviewStatusClass(application) {
  const status = getNormalizedInterviewStatus(application);

  if (status === "complete") {
    return "status-pass";
  }

  if (status === "partial") {
    return "status-processing";
  }

  return "status-muted";
}


