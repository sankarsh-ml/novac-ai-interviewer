import { useEffect, useState } from "react";

import "../styles/AtsScreeningPage.css";


function AtsScreeningPage({ applicationSummary, onBackHome, onPassed }) {
  const [loading, setLoading] = useState(Boolean(applicationSummary));
  const [atsResult, setAtsResult] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!applicationSummary?.application_id) {
      return;
    }

    runATS();
  }, [applicationSummary?.application_id]);

  const runATS = async () => {
    try {
      setLoading(true);
      setError("");

      const response = await fetch(
        `http://127.0.0.1:8000/api/ats/score/${applicationSummary.application_id}`
      );
      const data = await response.json();

      if (response.ok && data.success) {
        const result = data.result || data;
        console.log("ATS result:", result);
        setAtsResult(result);
      } else {
        setError(data?.detail || data?.message || "ATS scoring failed");
      }
    } catch (apiError) {
      console.error(apiError);
      setError("Could not connect to ATS service");
    } finally {
      setLoading(false);
    }
  };

  if (!applicationSummary) {
    return (
      <main className="ats-page">
        <section className="ats-panel">
          <h1>ATS Screening</h1>
          <p className="ats-message">No resume application is available.</p>
          <button className="ats-home-button" type="button" onClick={onBackHome}>
            Back Home
          </button>
        </section>
      </main>
    );
  }

  if (loading) {
    return (
      <main className="ats-page">
        <section className="ats-panel">
          <h1>Running ATS Screening...</h1>
          <p className="ats-message">Please wait while we evaluate the resume.</p>
        </section>
      </main>
    );
  }

  if (error) {
    return (
      <main className="ats-page">
        <section className="ats-panel">
          <h1>ATS Screening</h1>
          <p className="error-message">{error}</p>
          <button className="ats-home-button" type="button" onClick={onBackHome}>
            Back Home
          </button>
        </section>
        </main>
    );
  }

  const passed = getAtsPassed(atsResult);
  return (
    <main className="ats-page">
      <section className="ats-panel">

        {passed ? (
          <>
            <h1>🎉 Congratulations!</h1>

            <p className="ats-message">
              Your resume has successfully cleared the ATS screening stage.
            </p>

            <p className="ats-message">
              You may proceed to Aadhaar verification.
            </p>

            <button
              className="decision-button passed"
              onClick={onPassed}
            >
              Continue
            </button>
          </>
        ) : (
          <>
            <h1>Application Not Shortlisted</h1>

            <p className="ats-message">
              Thank you for applying.
            </p>

            <p className="ats-message">
              Your profile did not meet the current requirements for this role.
            </p>

            <button
              className="decision-button failed"
              onClick={onBackHome}
            >
              Back Home
            </button>
          </>
        )}

      </section>
    </main>
  );
}


function SummaryItem({ label, value }) {
  return (
    <article className="ats-summary-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}


function SkillsSection({ title, skills, className, emptyText }) {
  return (
    <div className="skills-section">
      <h2>{title}</h2>
      <div className="skill-list">
        {skills.length > 0 ? (
          skills.map((skill) => (
            <span key={skill} className={`skill-chip ${className}`}>
              {skill}
            </span>
          ))
        ) : (
          <p>{emptyText}</p>
        )}
      </div>
    </div>
  );
}


function getAtsScore(result) {
  return Number(result?.ats_score ?? result?.atsScore ?? result?.final_score ?? 0);
}


function getMatchedSkills(result) {
  return result?.matched_skills ?? result?.matchedSkills ?? [];
}


function getMissingSkills(result) {
  return result?.missing_skills ?? result?.missingSkills ?? [];
}


function getAtsPassed(result) {
  const score = getAtsScore(result);
  const status = String(result?.status ?? result?.ats_status ?? "").toLowerCase();

  return (
    result?.passed === true ||
    result?.atsPassed === true ||
    status === "passed" ||
    score >= 70
  );
}


export default AtsScreeningPage;
