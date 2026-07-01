import { useEffect, useState } from "react";
import { deleteJob, getJobs } from "../services/jobApi.js";

function CurrentJobsPage({
  onBack,
  onViewApplications,onUploadResumes,onQuestionBank,onViewQuestionBank
}) {
  const [jobs, setJobs] = useState([]);

  useEffect(() => {
    fetchJobs();
  }, []);

  const fetchJobs = async () => {
    try {
      const data = await getJobs();

      if (data.success) {
        setJobs(data.jobs || []);
      }
    } catch (error) {
      console.error(
        "Failed to fetch jobs:",
        error
      );
    }
  };

  const handleDeleteJob = async (jobId, jobTitle) => {
    const confirmed = window.confirm(
      `Are you sure you want to delete "${jobTitle}"?\n\nThis will permanently delete:\n\n• The job\n• All applications\n• Uploaded resumes\n• Interview recordings\n• Interview transcripts\n• Candidate reports\n\nThis action cannot be undone.`
    );

    if (!confirmed) return;

    try {
      const data = await deleteJob(jobId);

      if (data.success) {
        alert("Job deleted successfully.");
        fetchJobs(); // Refresh the list
      } else {
        alert(data.message || "Failed to delete job.");
      }
    } catch (error) {
      console.error(error);
      alert("Something went wrong.");
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

        <div className="hr-header">
          <h1>Current Jobs</h1>
        </div>

        {jobs.length === 0 ? (
          <p>No jobs found.</p>
        ) : (
          <div className="jobs-list">

            {jobs.map((job) => (
              <div
                key={job.id}
                className="job-card"
              >
                <h3>{job.title}</h3>

                <p>
                  {job.description}
                </p>

                <p>
                  <strong>Skills:</strong>{" "}
                  {job.required_skills?.join(", ")}
                </p>

                <p>
                  <strong>Education:</strong>{" "}
                  {job.education}
                </p>

                <p>
                  <strong>Experience:</strong>{" "}
                  {job.experience} years
                </p>

                <div className="job-actions">

                <button
                  className="hr-button"
                  onClick={() =>
                    onViewApplications(job)
                  }
                >
                  View Applications
                </button>

                <button 
                  className="upload-button"
                  onClick={() =>
                    onUploadResumes(job)
                  }
                >
                  Upload Resumes
                </button>

                <button
                  className="hr-button"
                  onClick={() => onQuestionBank(job)}
                >
                  Upload Question Bank
                </button>

                <button
                  className="hr-button"
                  onClick={() => onViewQuestionBank(job)}
                >
                  View Question Bank
                </button>

                <button
                  className="delete-button"
                  onClick={() =>
                    handleDeleteJob(job.id, job.title)
                  }
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
