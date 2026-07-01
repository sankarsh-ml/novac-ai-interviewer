import { getResumeViewUrl } from "../services/resumeApi.js";
import "../styles/ResumeViewerPage.css";

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
        src={getResumeViewUrl(application.application_id)}
      />

    </main>
  );
}

export default ResumeViewerPage;
