import { useEffect, useState } from "react";

function CurrentJobsPage({
  onBack,
  onViewApplications,onUploadResumes,onQuestionBank
}) {
  const [jobs, setJobs] = useState([]);

  useEffect(() => {
    fetchJobs();
  }, []);

  const fetchJobs = async () => {
    try {
      const response = await fetch(
        "http://127.0.0.1:8000/api/hr/jobs"
      );

      const data = await response.json();

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
                  onClick={() => onQuestionBank(job)}
                >
                  View Question Bank
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
