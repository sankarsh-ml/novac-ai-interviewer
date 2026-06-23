import { useEffect, useState } from "react";
import "../styles/JobApplicationsPage.css";
function JobApplicationsPage({
  job,
  onBack
}) {

  const [applications, setApplications] =
    useState([]);

  useEffect(() => {
    fetchApplications();
  }, []);

  const fetchApplications = async () => {

    try {

      const response =
        await fetch(
          `http://127.0.0.1:8000/api/hr/jobs/${job.id}/applications`
        );

      const data =
        await response.json();

      if (data.success) {

        setApplications(
          data.applications || []
        );
      }

    } catch (error) {

      console.error(error);
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

      <h1>
        {job.title}
      </h1>

      <div className="job-summary">

        <div className="summary-card">
          <span>Total Applications</span>
          <strong>
            {applications.length}
          </strong>
        </div>

        <div className="summary-card">
          <span>Passed</span>
          <strong>
            {
              applications.filter(
                app =>
                  app.ats_status === "passed"
              ).length
            }
          </strong>
        </div>

        <div className="summary-card">
          <span>Failed</span>
          <strong>
            {
              applications.filter(
                app =>
                  app.ats_status === "failed"
              ).length
            }
          </strong>
        </div>

      </div>

      <div className="table-wrapper">

        <table className="applications-table">

          <thead>

            <tr>

              <th>Candidate</th>

              <th>ATS</th>

              <th>Semantic</th>

              <th>Skill</th>

              <th>Education</th>

              <th>Experience</th>

              <th>Project</th>

              <th>Status</th>

            </tr>

          </thead>

          <tbody>

            {applications.map(
              (app) => (

                <tr
                  key={
                    app.application_id
                  }
                >

                  <td>
                    {
                      app.candidate_name
                    }
                  </td>

                  <td>
                    {
                      app.ats_score ?? "-"
                    }
                  </td>

                  <td>
                    {
                      app.semantic_score ?? "-"
                    }
                  </td>

                  <td>
                    {
                      app.skill_score ?? "-"
                    }
                  </td>

                  <td>
                    {
                      app.education_score ?? "-"
                    }
                  </td>

                  <td>
                    {
                      app.experience_score ?? "-"
                    }
                  </td>

                  <td>
                    {
                      app.project_score ?? "-"
                    }
                  </td>

                  <td>

                    <span
                      className={
                        app.ats_status === "passed"
                          ? "status-pass"
                          : "status-fail"
                      }
                    >
                      {
                        app.ats_status
                      }
                    </span>

                  </td>

                </tr>

              )
            )}

          </tbody>

        </table>

      </div>

    </div>

  </main>

);
}

export default JobApplicationsPage;