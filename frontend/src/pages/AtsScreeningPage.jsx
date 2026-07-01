import { useEffect, useState } from "react";

import { scoreResume } from "../services/resumeApi.js";
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

      const data = await scoreResume(applicationSummary.application_id);

      if (data.success) {
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

  const atsScore = getAtsScore(atsResult);
  const matchedSkills = getMatchedSkills(atsResult);
  const missingSkills = getMissingSkills(atsResult);
  const passed = getAtsPassed(atsResult);
  console.log("Computed pass:", passed);

  return (
    <main className="ats-page">
      <section className="ats-panel">
        <p className="eyebrow">Screening Pipeline</p>
        <h1>ATS Screening Result</h1>

        <div className="ats-summary-grid">
          <SummaryItem label="Candidate" value={atsResult?.candidate_name || "--"} />
          <SummaryItem label="ATS Score" value={`${atsScore}%`} />
          <SummaryItem label="Matched Skills" value={matchedSkills.length} />
          <SummaryItem label="Missing Skills" value={missingSkills.length} />
        </div>

        <div className={`result-banner ${passed ? "passed" : "failed"}`}>
          <h2>{passed ? "ATS Passed" : "ATS Failed"}</h2>
          <p>
            ATS Score: <strong>{atsScore}%</strong>
          </p>
        </div>

        <SkillsSection
          title="Matched Skills"
          skills={matchedSkills}
          className="matched"
          emptyText="No matched skills"
        />
        <SkillsSection
          title="Missing Skills"
          skills={missingSkills}
          className="missing"
          emptyText="No missing skills"
        />

        <div className="decision-actions">
          {passed ? (
            <button className="decision-button passed" type="button" onClick={onPassed}>
              Continue to Government ID Verification
            </button>
          ) : (
            <button className="decision-button failed" type="button" onClick={onBackHome}>
              Back Home
            </button>
          )}
        </div>
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
