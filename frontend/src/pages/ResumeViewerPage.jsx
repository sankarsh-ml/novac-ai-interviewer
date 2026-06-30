import "../styles/ResumeViewerPage.css";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function ResumeViewerPage({ application, onBack }) {
  if (!application) return null;

  return (
    <main className="resume-viewer-page">

      <div className="resume-header">

        <button
          className="back-button"
          onClick={onBack}
        >
          ← Back
        </button>

        <div>
          <h1>{application.candidate_name}</h1>
          <p>{application.email}</p>
        </div>

      </div>

      <iframe
        title="Candidate Resume"
        className="resume-frame"
        src={`${API_BASE_URL}/api/hr/applications/${application.application_id}/resume/view`}
      />

    </main>
  );
}

export default ResumeViewerPage;