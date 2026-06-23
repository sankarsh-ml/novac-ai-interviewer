import { useEffect, useState } from "react";

import "../styles/HRDashboardPage.css";


function HRDashboardPage({ onBack }) {
  const [title, setTitle] = useState("");
  const [skills, setSkills] = useState("");
  const [education, setEducation] = useState("");
  const [experience, setExperience] = useState("");
  const [keywords, setKeywords] = useState("");
  const [jobs, setJobs] = useState([]);
  const [interviewResults, setInterviewResults] = useState([]);
  const [isLoadingResults, setIsLoadingResults] = useState(false);

  useEffect(() => {
    fetchJobs();
    fetchInterviewResults();
  }, []);

  const fetchJobs = async () => {
    try {
      const response = await fetch("http://127.0.0.1:8000/api/hr/jobs");
      const data = await response.json();

      if (data.success) {
        setJobs(data.jobs);
      }
    } catch (error) {
      console.error("Error fetching jobs:", error);
    }
  };

  const addJob = async () => {
    if (
      !title.trim() ||
      !skills.trim() ||
      !education.trim() ||
      !experience.trim() ||
      !keywords.trim()
    ) {
      alert("Please fill all fields");
      return;
    }

    try {
      const response = await fetch("http://127.0.0.1:8000/api/hr/jobs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          title,
          required_skills: skills
            .split(",")
            .map((skill) => skill.trim())
            .filter(Boolean),
          education,
          experience: Number(experience),
          keywords: keywords
            .split(",")
            .map((keyword) => keyword.trim())
            .filter(Boolean),
        }),
      });

      const data = await response.json();

      if (data.success) {
        setTitle("");
        setSkills("");
        setEducation("");
        setExperience("");
        setKeywords("");
        fetchJobs();
      }
    } catch (error) {
      console.error("Error adding job:", error);
    }
  };

  const fetchInterviewResults = async () => {
    setIsLoadingResults(true);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/hr/interviews/results");
      const data = await response.json();
      setInterviewResults(data.success && Array.isArray(data.results) ? data.results : []);
    } catch (error) {
      console.error("Error fetching interview results:", error);
    } finally {
      setIsLoadingResults(false);
    }
  };

  return (
    <main className="hr-page">
      <div className="hr-container">
        <button className="back-button" type="button" onClick={onBack}>
          Back
        </button>

        <div className="hr-header">
          <p className="eyebrow">Admin</p>
          <h1>HR Dashboard</h1>
        </div>

        <div className="hr-panel">
          <h2>Add Job</h2>

          <input
            className="hr-input"
            type="text"
            placeholder="Job Title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />

          <textarea
            className="hr-textarea"
            placeholder="Required Skills (comma separated)"
            value={skills}
            onChange={(event) => setSkills(event.target.value)}
          />

          <input
            className="hr-input"
            type="text"
            placeholder="Education Requirement"
            value={education}
            onChange={(event) => setEducation(event.target.value)}
          />

          <input
            className="hr-input"
            type="number"
            placeholder="Required Experience (Years)"
            value={experience}
            onChange={(event) => setExperience(event.target.value)}
          />

          <textarea
            className="hr-textarea"
            placeholder="Keywords (comma separated)"
            value={keywords}
            onChange={(event) => setKeywords(event.target.value)}
          />

          <button className="hr-button" type="button" onClick={addJob}>
            Add Job
          </button>
        </div>

        <div className="jobs-section">
          <h2>Current Jobs</h2>

          <div className="jobs-list">
            {jobs.length === 0 ? (
              <p>No jobs added yet.</p>
            ) : (
              jobs.map((job) => (
                <div key={job.id} className="job-card">
                  <h3>{job.title}</h3>
                  <p>
                    <strong>Skills:</strong> {job.required_skills?.join(", ")}
                  </p>
                  <p>
                    <strong>Education:</strong> {job.education}
                  </p>
                  <p>
                    <strong>Experience:</strong> {job.experience}
                  </p>
                  <p>
                    <strong>Keywords:</strong> {job.keywords?.join(", ")}
                  </p>
                  <small>Job ID: {job.id}</small>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="interview-results-section">
          <div className="section-heading-row">
            <h2>Interview Results</h2>
            <button className="hr-secondary-button" type="button" onClick={fetchInterviewResults}>
              Refresh
            </button>
          </div>

          <div className="interview-results-list">
            {isLoadingResults ? (
              <p>Loading interview results...</p>
            ) : interviewResults.length === 0 ? (
              <p>No interview results available yet.</p>
            ) : (
              interviewResults.map((result) => (
                <InterviewResultCard key={result.session_id} result={result} />
              ))
            )}
          </div>
        </div>
      </div>
    </main>
  );
}


function InterviewResultCard({ result }) {
  const candidate = result.candidate_info || {};
  const questions = Array.isArray(result.questions) ? result.questions : [];

  return (
    <article className="interview-result-card">
      <header className="result-card-header">
        <div>
          <h3>{candidate.candidate_name || "Candidate"}</h3>
          <p>Session ID: {result.session_id}</p>
          {candidate.file_name && <p>Resume: {candidate.file_name}</p>}
        </div>
        <div className="total-score-box">
          <span>Total score</span>
          <strong>{result.total_score ?? 0}/{result.max_score ?? 50}</strong>
          <small>{result.status || "not_started"}</small>
        </div>
      </header>

      <div className="result-question-list">
        {questions.map((question, index) => (
          <section className="result-question" key={question.question_id || index}>
            <div className="result-question-topline">
              <span>Q{index + 1}</span>
              {question.difficulty && <b>{question.difficulty}</b>}
              <strong>{question.score ?? 0}/10</strong>
            </div>
            <p className="result-question-text">{question.question_text}</p>
            <p><strong>Transcript:</strong> {question.transcript || "Not submitted yet."}</p>
            <p><strong>Feedback:</strong> {question.feedback || "No feedback stored."}</p>
            {question.transcript_file_path && (
              <p className="path-line"><strong>Transcript file:</strong> {question.transcript_file_path}</p>
            )}
            {question.audio_file_path && (
              <p className="path-line"><strong>Audio file:</strong> {question.audio_file_path}</p>
            )}
          </section>
        ))}
      </div>
    </article>
  );
}


export default HRDashboardPage;
