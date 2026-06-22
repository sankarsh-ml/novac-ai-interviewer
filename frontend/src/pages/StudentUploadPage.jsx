import { useEffect, useState } from "react";

import { uploadResume } from "../api/resumeApi.js";
import "../styles/StudentUploadPage.css";


function StudentUploadPage({ onBack, onUploadSuccess }) {
  const [file, setFile] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchJobs();
  }, []);

  const fetchJobs = async () => {
    try {
      const response = await fetch("http://127.0.0.1:8000/api/hr/jobs");
      const data = await response.json();

      if (data.success) {
        setJobs(data.jobs);
      }
    } catch (apiError) {
      console.error("Failed to fetch jobs:", apiError);
    }
  };

  const handleFileChange = (event) => {
    const selectedFile = event.target.files?.[0] || null;
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
    if (!selectedJob) {
      setError("Please select a job first.");
      return;
    }

    if (!file) {
      setError("Please select a PDF resume before uploading.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await uploadResume(file, selectedJob);
      onUploadSuccess(response.data);
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
          <p className="upload-subtitle">
            Your resume will be parsed and stored for ATS screening.
          </p>
        </header>

        <section className="upload-panel">
          <div className="job-selection">
            <h2>Available Jobs</h2>
            {jobs.length === 0 ? (
              <p>No jobs available. Ask HR to add a job first.</p>
            ) : (
              jobs.map((job) => (
                <label className="job-option" key={job.id}>
                  <input
                    type="radio"
                    name="job"
                    value={job.id}
                    checked={selectedJob === job.id}
                    onChange={() => setSelectedJob(job.id)}
                  />
                  <span>
                    <strong>{job.title}</strong>
                    <small>{job.required_skills?.join(", ")}</small>
                  </span>
                </label>
              ))
            )}
          </div>

          <label className="file-input-label" htmlFor="resume-file">
            <span>{file ? file.name : "Select a PDF resume"}</span>
            <input id="resume-file" type="file" accept=".pdf,application/pdf" onChange={handleFileChange} />
          </label>

          <button className="upload-button" type="button" onClick={handleUpload} disabled={loading}>
            {loading ? "Uploading..." : "Upload"}
          </button>
        </section>

        {error && <p className="error-message">{error}</p>}

        {!loading && (
          <p className="empty-message">
            No resume uploaded yet. After upload, you will continue to ATS screening.
          </p>
        )}
      </section>
    </main>
  );
}


export default StudentUploadPage;
