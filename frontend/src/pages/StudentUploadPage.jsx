import { useState } from "react";

import { uploadResume } from "../api/resumeApi.js";
import "../styles/StudentUploadPage.css";


function StudentUploadPage({ onBack }) {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const resumeData = result?.data;
  const sections = resumeData?.ats_ready_data?.sections_detected || {};

  const handleFileChange = (event) => {
    const selectedFile = event.target.files?.[0] || null;
    setResult(null);
    setError("");

    if (!selectedFile) {
      setFile(null);
      return;
    }

    if (!selectedFile.name.toLowerCase().endsWith(".pdf")) {
      setFile(null);
      setError("Please choose a PDF resume.");
      return;
    }

    setFile(selectedFile);
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please select a PDF resume before uploading.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await uploadResume(file);
      setResult(response);
    } catch (apiError) {
      setError(apiError.message || "Could not upload resume.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="upload-page">
      <section className="upload-container">
        <button className="back-button" type="button" onClick={onBack}>
          Back
        </button>

        <header className="upload-header">
          <p className="eyebrow">Student</p>
          <h1>Upload Resume</h1>
        </header>

        <section className="upload-panel">
          <label className="file-input-label" htmlFor="resume-file">
            <span>{file ? file.name : "Select a PDF resume"}</span>
            <input id="resume-file" type="file" accept=".pdf,application/pdf" onChange={handleFileChange} />
          </label>

          <button className="upload-button" type="button" onClick={handleUpload} disabled={loading}>
            {loading ? "Uploading..." : "Upload"}
          </button>
        </section>

        {error && <p className="error-message">{error}</p>}

        {!resumeData && !loading && (
          <p className="empty-message">No resume uploaded yet. Choose a PDF to extract resume text.</p>
        )}

        {resumeData && (
          <section className="results">
            <div className="stats-grid">
              <StatCard label="File name" value={resumeData.file_name} />
              <StatCard label="Total pages" value={resumeData.total_pages} />
              <StatCard label="Word count" value={resumeData.word_count} />
              <StatCard label="Text length" value={resumeData.text_length} />
            </div>

            <ResultBlock title="Skills">
              <SkillChips skills={sections.skills?.items || []} />
            </ResultBlock>

            <ResultBlock title="Education">
              <EducationCards education={sections.education?.items || []} />
            </ResultBlock>

            <ResultBlock title="Projects">
              <ProjectCards projects={sections.projects?.items || []} />
            </ResultBlock>

            <ResultBlock title="Experience">
              <ExperienceCards experience={sections.experience?.items || []} />
            </ResultBlock>

            <ResultBlock title="Certifications">
              <CertificationList certifications={sections.certifications?.items || []} />
            </ResultBlock>

            <ResultBlock title="Raw Extracted Text">
              <pre className="raw-text">{resumeData.extracted_text || "No text found."}</pre>
            </ResultBlock>
          </section>
        )}
      </section>
    </main>
  );
}


function StatCard({ label, value }) {
  return (
    <article className="stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}


function ResultBlock({ title, children }) {
  return (
    <section className="result-block">
      <h2>{title}</h2>
      {children}
    </section>
  );
}


function SkillChips({ skills }) {
  if (!skills.length) {
    return <p className="muted">No skills detected.</p>;
  }

  return (
    <div className="chip-list">
      {skills.map((skill) => (
        <span className="chip" key={skill}>{skill}</span>
      ))}
    </div>
  );
}


function EducationCards({ education }) {
  if (!education.length) {
    return <p className="muted">No education detected.</p>;
  }

  return (
    <div className="card-grid">
      {education.map((item, index) => (
        <article className="info-card" key={`${item.degree}-${index}`}>
          <h3>{item.degree || item.title || `Education ${index + 1}`}</h3>
          {item.institution && <p className="meta">{item.institution}</p>}
          {item.duration && <p className="meta">{item.duration}</p>}
          {item.description && <p>{item.description}</p>}
        </article>
      ))}
    </div>
  );
}


function ProjectCards({ projects }) {
  if (!projects.length) {
    return <p className="muted">No projects detected.</p>;
  }

  return (
    <div className="card-grid">
      {projects.map((project, index) => (
        <article className="info-card" key={`${project.title}-${index}`}>
          <h3>{project.title || `Project ${index + 1}`}</h3>
          {project.description && <p>{project.description}</p>}
          {project.technologies?.length > 0 && (
            <div className="mini-chip-list">
              {project.technologies.map((technology) => (
                <span key={technology}>{technology}</span>
              ))}
            </div>
          )}
        </article>
      ))}
    </div>
  );
}


function ExperienceCards({ experience }) {
  if (!experience.length) {
    return <p className="muted">No experience detected.</p>;
  }

  return (
    <div className="card-grid">
      {experience.map((item, index) => (
        <article className="info-card" key={`${item.title}-${index}`}>
          <h3>{item.title || `Experience ${index + 1}`}</h3>
          {item.company && <p className="meta">{item.company}</p>}
          {item.duration && <p className="meta">{item.duration}</p>}
          {item.description && <p>{item.description}</p>}
        </article>
      ))}
    </div>
  );
}


function CertificationList({ certifications }) {
  if (!certifications.length) {
    return <p className="muted">No certifications detected.</p>;
  }

  return (
    <ul className="cert-list">
      {certifications.map((certification) => (
        <li key={certification}>{certification}</li>
      ))}
    </ul>
  );
}


export default StudentUploadPage;
