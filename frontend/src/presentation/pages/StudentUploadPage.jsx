import { useEffect, useRef, useState } from "react";

import { fetchJobs } from "@application/useCases/jobUseCases.js";
import { uploadResume } from "@application/useCases/resumeUseCases.js";
import { useDependencies } from "@presentation/hooks/useDependencies.js";
import { PROCESSING_LEAVE_MESSAGE } from "@shared/constants/appMessages.js";
import "@presentation/styles/StudentUploadPage.css";

function StudentUploadPage({ onBack, onUploadSuccess }) {
  const { jobRepository, resumeRepository } = useDependencies();
  const isMountedRef = useRef(true);
  const loadingRef = useRef(false);
  const [file, setFile] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchJobs();

    return () => {
      isMountedRef.current = false;
      loadingRef.current = false;
    };
  }, []);

  useEffect(() => {
    loadingRef.current = loading;
  }, [loading]);

  useEffect(() => {
    if (!loading) {
      return;
    }

    const handleBeforeUnload = (event) => {
      event.preventDefault();
      event.returnValue = PROCESSING_LEAVE_MESSAGE;
      return PROCESSING_LEAVE_MESSAGE;
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [loading]);

  useEffect(() => {
    window.history.pushState({ studentUploadPage: true }, "", window.location.href);

    const handlePopState = () => {
      if (!loadingRef.current) {
        onBack();
        return;
      }

      if (window.confirm(PROCESSING_LEAVE_MESSAGE)) {
        loadingRef.current = false;
        onBack();
        return;
      }

      window.history.pushState({ studentUploadPage: true }, "", window.location.href);
    };

    window.addEventListener("popstate", handlePopState);

    return () => {
      window.removeEventListener("popstate", handlePopState);
    };
  }, [onBack]);

  const fetchJobs = async () => {
    try {
      const data = await fetchJobs(jobRepository);

      if (data.success && isMountedRef.current) {
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
      const response = await uploadResume(resumeRepository, file, selectedJob);

      if (isMountedRef.current) {
        onUploadSuccess(response.data);
      }
    } catch (apiError) {
      if (isMountedRef.current) {
        setError(apiError.message || "Could not upload resume.");
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
      loadingRef.current = false;
    }
  };

  const handleBack = () => {
    if (loadingRef.current && !window.confirm(PROCESSING_LEAVE_MESSAGE)) {
      return;
    }

    loadingRef.current = false;
    onBack();
  };

  return (
    <main className="upload-page">
      <section className="upload-container">
        <button className="back-button" type="button" onClick={handleBack}>
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
