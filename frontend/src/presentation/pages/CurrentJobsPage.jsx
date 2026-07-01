import { useEffect, useState } from "react";
import {
  deleteJob,
  fetchJobs as fetchJobsUseCase,
} from "@application/useCases/jobUseCases.js";
import { useDependencies } from "@presentation/hooks/useDependencies.js";

function CurrentJobsPage({
  onBack,
  onViewApplications,
  onUploadResumes,
  onQuestionBank,
  onViewQuestionBank,
}) {
  const { jobRepository } = useDependencies();

  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadJobs();
  }, []);

  const loadJobs = async () => {
    try {
      setLoading(true);
      setError("");

      const data = await fetchJobsUseCase(jobRepository);
      console.log("Current Jobs API response:", data);

      const jobsList = extractJobs(data).map(normalizeJob);
      setJobs(jobsList);
    } catch (err) {
      console.error("Failed to fetch jobs:", err);
      setError(err.message || "Failed to fetch jobs.");
      setJobs([]);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteJob = async (jobId, jobTitle) => {
    const confirmed = window.confirm(
      `Are you sure you want to delete "${jobTitle}"?\n\nThis will permanently delete:\n\n• The job\n• All applications\n• Uploaded resumes\n• Interview recordings\n• Interview transcripts\n• Candidate reports\n\nThis action cannot be undone.`
    );

    if (!confirmed) {
      return;
    }

    try {
      const data = await deleteJob(jobRepository, jobId);

      if (data.success === false) {
        alert(data.message || "Failed to delete job.");
        return;
      }

      alert("Job deleted successfully.");
      await loadJobs();
    } catch (err) {
      console.error(err);
      alert(err.message || "Something went wrong.");
    }
  };

  return (
    <main className="hr-page">
      <div className="hr-container">
        <button className="back-button" type="button" onClick={onBack}>
          Back
        </button>

        <div className="hr-header">
          <h1>Current Jobs</h1>
        </div>

        {loading && <p>Loading jobs...</p>}

        {!loading && error && <p className="error-message">{error}</p>}

        {!loading && !error && jobs.length === 0 ? (
          <p>No jobs found.</p>
        ) : null}

        {!loading && !error && jobs.length > 0 && (
          <div className="jobs-list">
            {jobs.map((job, index) => (
              <div key={job.id || index} className="job-card">
                <h3>{job.title || "Untitled Job"}</h3>

                <p>{job.description || "No description available."}</p>

                <p>
                  <strong>Skills:</strong>{" "}
                  {job.required_skills.length
                    ? job.required_skills.join(", ")
                    : "Not specified"}
                </p>

                <p>
                  <strong>Education:</strong>{" "}
                  {job.education || "Not specified"}
                </p>

                <p>
                  <strong>Experience:</strong>{" "}
                  {job.experience !== "" && job.experience !== null
                    ? `${job.experience} years`
                    : "Not specified"}
                </p>

                <div className="job-actions">
                  <button
                    className="hr-button"
                    type="button"
                    onClick={() => onViewApplications(job)}
                  >
                    View Applications
                  </button>

                  <button
                    className="upload-button"
                    type="button"
                    onClick={() => onUploadResumes(job)}
                  >
                    Upload Resumes
                  </button>

                  <button
                    className="hr-button"
                    type="button"
                    onClick={() => onQuestionBank(job)}
                  >
                    Upload Question Bank
                  </button>

                  <button
                    className="hr-button"
                    type="button"
                    onClick={() => onViewQuestionBank(job)}
                  >
                    View Question Bank
                  </button>

                  <button
                    className="delete-button"
                    type="button"
                    onClick={() => handleDeleteJob(job.id, job.title)}
                    disabled={!job.id}
                  >
                    Delete Job
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

export default CurrentJobsPage;

function extractJobs(data) {
  if (Array.isArray(data)) {
    return data;
  }

  if (Array.isArray(data?.jobs)) {
    return data.jobs;
  }

  if (Array.isArray(data?.data)) {
    return data.data;
  }

  if (Array.isArray(data?.data?.jobs)) {
    return data.data.jobs;
  }

  if (Array.isArray(data?.result)) {
    return data.result;
  }

  if (Array.isArray(data?.result?.jobs)) {
    return data.result.jobs;
  }

  return [];
}

function normalizeJob(job = {}) {
  const skills =
    job.required_skills ||
    job.requiredSkills ||
    job.skills ||
    [];

  return {
    ...job,
    id: String(job.id || job._id || job.job_id || ""),
    title: job.title || job.job_title || job.name || "",
    description: job.description || job.job_description || "",
    required_skills: Array.isArray(skills)
      ? skills
      : String(skills || "")
          .split(",")
          .map((skill) => skill.trim())
          .filter(Boolean),
    education:
      job.education ||
      job.education_requirement ||
      job.educationRequirement ||
      "",
    experience:
      job.experience ??
      job.required_experience ??
      job.requiredExperience ??
      "",
    keywords: Array.isArray(job.keywords)
      ? job.keywords
      : String(job.keywords || "")
          .split(",")
          .map((keyword) => keyword.trim())
          .filter(Boolean),
  };
}