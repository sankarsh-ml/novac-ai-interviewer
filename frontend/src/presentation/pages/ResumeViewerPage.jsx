import { getResumeViewUrl } from "@application/useCases/resumeUseCases.js";
import { useDependencies } from "@presentation/hooks/useDependencies.js";
import "@presentation/styles/ResumeViewerPage.css";

function ResumeViewerPage({ application, onBack }) {
  const { resumeRepository } = useDependencies();

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
        src={getResumeViewUrl(resumeRepository, application.application_id)}
      />

    </main>
  );
}

export default ResumeViewerPage;
