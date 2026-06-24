import { useEffect, useState } from "react";
import "../styles/ShortlistedCandidatesPage.css";

function ShortlistedCandidatesPage({job,onBack}) {

  const [applications, setApplications] =
    useState([]);

  const [expiryDates, setExpiryDates] =
    useState({});

  const [generatedLinks, setGeneratedLinks] =
    useState({});

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

          const passedCandidates =
            (data.applications || []).filter(
              app =>
                app.ats_status === "passed"
            );

          setApplications(
            passedCandidates
          );

          const links = {};

          const dates = {};

          passedCandidates.forEach(
            (app) => {

              if (
                app.interview_link
              ) {

                links[
                  app.application_id
                ] =
                  app.interview_link;
              }

              if (
                app.expiry_date
              ) {

                dates[
                  app.application_id
                ] =
                  app.expiry_date;
              }
            }
          );

          setGeneratedLinks(
            links
          );

          setExpiryDates(
            dates
          );
      }

    } catch (error) {

      console.error(error);
    }
  };

  const generateInterviewLink = async (application) => {

    const expiry =
        expiryDates[
        application.application_id
        ];

    if (!expiry) {

        alert(
        "Please select an expiry date first."
        );

        return;
    }

    try {

        const response =
        await fetch(
            "http://127.0.0.1:8000/api/interview/create-link",
            {
            method: "POST",

            headers: {
                "Content-Type":
                "application/json"
            },

            body: JSON.stringify({
                application_id:
                application.application_id,

                candidate_name:
                application.candidate_name,

                email:
                application.email,

                expiry_date:
                expiry
            })
            }
        );

        const data =
        await response.json();

        if (data.success) {

        setGeneratedLinks({
            ...generatedLinks,
            [application.application_id]:
            data.link
        });

        navigator.clipboard.writeText(
            data.link
        );

        alert(
            "Interview Link Generated & Stored"
        );
        }

    } catch (error) {

            console.error(
                "FULL ERROR:",
                error
            );

            alert(
                "Failed To Generate Link"
            );
            }
    };

  return (

    <main className="shortlisted-page">

      <div className="shortlisted-container">

        <button
          className="back-button"
          onClick={onBack}
        >
          ← Back
        </button>

        <div className="shortlisted-header">

          <h1>
            Shortlisted Candidates
          </h1>

          <p>
            {job.title}
          </p>

        </div>

        <div className="summary-card">

          <span>
            Total Shortlisted
          </span>

          <strong>
            {applications.length}
          </strong>

        </div>

        <div className="table-wrapper">

          <table
            className="shortlisted-table"
          >

            <thead>

              <tr>

                <th>
                  Candidate
                </th>

                <th>
                  Email
                </th>

                <th>
                  ATS Score
                </th>

                <th>
                  Expiry Date
                </th>

                <th>
                  Generate
                </th>

                <th>
                  Interview Link
                </th>

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
                        app.email ||
                        "Not Available"
                      }
                    </td>

                    <td>
                      {
                        app.ats_score
                      }
                    </td>

                    <td>

                      <input
                        type="date"
                        className="expiry-input"
                        value={
                          expiryDates[
                            app.application_id
                          ] || ""
                        }
                        onChange={(e) =>
                          setExpiryDates({
                            ...expiryDates,
                            [app.application_id]:
                              e.target.value
                          })
                        }
                      />

                    </td>

                    <td>

                      <button
                        className="send-button"
                        onClick={() =>
                          generateInterviewLink(
                            app
                          )
                        }
                      >
                        Generate Link
                      </button>

                    </td>

                    <td>

                      {
                        generatedLinks[
                          app.application_id
                        ] ? (

                          <div
                            className="generated-link"
                          >
                            {
                              generatedLinks[
                                app.application_id
                              ]
                            }
                          </div>

                        ) : (

                          <span
                            className="no-link"
                          >
                            Not Generated
                          </span>

                        )
                      }

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

export default ShortlistedCandidatesPage;