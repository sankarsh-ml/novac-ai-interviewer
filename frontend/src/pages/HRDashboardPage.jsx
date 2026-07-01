import { useEffect, useState } from "react";

import { createJob, getJobs } from "../services/jobApi.js";
import "../styles/HRDashboardPage.css";


function HRDashboardPage({ onBack }) {
  const [title, setTitle] = useState("");
  const [skills, setSkills] = useState("");
  const [education, setEducation] = useState("");
  const [experience, setExperience] = useState("");
  const [keywords, setKeywords] = useState("");
  const [jobs, setJobs] = useState([]);
  const [description, setDescription] = useState("");

  useEffect(() => {
    fetchJobs();
  }, []);

  const fetchJobs = async () => {
    try {
      const data = await getJobs();

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
      !description.trim() ||
      !skills.trim() ||
      !education.trim() ||
      !experience.trim() ||
      !keywords.trim()
    ) {
      alert("Please fill all fields");
      return;
    }

    try {
      const data = await createJob({
        title,
        description,
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
      });

      if (data.success) {
        setTitle("");
        setDescription("");
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
            placeholder="Job Description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
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
                    <strong>Description:</strong> {job.description}
                  </p>
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
      </div>
    </main>
  );
}


export default HRDashboardPage;
