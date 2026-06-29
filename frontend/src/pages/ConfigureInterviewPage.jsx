import { useEffect, useMemo, useState } from "react";
import "../styles/ConfigureInterviewPage.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function ConfigureInterviewPage({ applicationId, onBack }) {
  const [application, setApplication] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [filters, setFilters] = useState({
    difficulty: "all",
    area_of_interest: "all",
    search: "",
    job_role: "all",
  });
  const [interviewDate, setInterviewDate] = useState("");
  const [interviewTime, setInterviewTime] = useState("");
  const [questionCount, setQuestionCount] = useState("");
  const [selectedIds, setSelectedIds] = useState([]);
  const [message, setMessage] = useState("");
  const [generatedLink, setGeneratedLink] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!applicationId) {
      setLoading(false);
      setMessage("Candidate ID is missing.");
      return;
    }

    loadConfigureData();
  }, [applicationId]);

  const loadConfigureData = async () => {
    setLoading(true);
    setMessage("");

    try {
      const response = await fetch(`${API_BASE_URL}/api/interviews/${encodeURIComponent(applicationId)}/configure-data`);
      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.detail || data.message || "Could not load interview configuration.");
      }

      setApplication(data.application || {});
      setQuestions(Array.isArray(data.questions) ? data.questions : []);
      setInterviewDate(data.application?.interview_date || getDateFromIso(data.application?.interview_scheduled_at) || "");
      setInterviewTime(data.application?.interview_time || getTimeFromIso(data.application?.interview_scheduled_at) || "");
      setQuestionCount(data.interview_config?.number_of_questions || "");
      setSelectedIds(data.interview_config?.selected_question_ids || []);
      setGeneratedLink(data.application?.interview_link || "");
    } catch (error) {
      setMessage(error.message || "Could not load interview configuration.");
    } finally {
      setLoading(false);
    }
  };

  const areas = useMemo(
    () => Array.from(new Set(questions.map((question) => getQuestionArea(question)))).sort(),
    [questions]
  );
  const jobRoles = useMemo(
    () => Array.from(new Set(questions.map((question) => question.job_role || question.jobRole || "").filter(Boolean))).sort(),
    [questions]
  );
  const filteredQuestions = questions.filter((question) => {
    const search = filters.search.trim().toLowerCase();
    const tags = Array.isArray(question.tags) ? question.tags.join(" ") : "";
    const haystack = [
      question.question,
      question.expected_answer || question.expectedAnswer,
      getQuestionArea(question),
      tags,
      question.job_role || question.jobRole || ""
    ].join(" ").toLowerCase();

    return (
      (filters.difficulty === "all" || normalizeDifficulty(question.difficulty) === filters.difficulty) &&
      (filters.area_of_interest === "all" || getQuestionArea(question) === filters.area_of_interest) &&
      (filters.job_role === "all" || (question.job_role || question.jobRole || "") === filters.job_role) &&
      (!search || haystack.includes(search))
    );
  });
  const selectedQuestions = selectedIds
    .map((id) => questions.find((question) => getQuestionId(question) === id))
    .filter(Boolean);
  const requiredCount = Number(questionCount || 0);
  const hasGeneratedLink = Boolean(
    application?.interview_link_generated ||
    application?.interview_link ||
    generatedLink
  );
  const selectedExceedsLimit = requiredCount > 0 && selectedIds.length > requiredCount;
  const selectedAtLimit = requiredCount > 0 && selectedIds.length >= requiredCount;
  const canGenerate =
    Boolean(interviewDate) &&
    Boolean(interviewTime) &&
    requiredCount > 0 &&
    selectedIds.length === requiredCount &&
    !isInterviewLocked(application) &&
    !hasGeneratedLink;

  const toggleQuestion = (question) => {
    const questionId = getQuestionId(question);

    if (!questionId) {
      return;
    }

    if (selectedIds.includes(questionId)) {
      if (hasGeneratedLink) {
        setMessage("Interview link has already been generated. Selected questions are frozen.");
        return;
      }

      setSelectedIds(selectedIds.filter((id) => id !== questionId));
      return;
    }

    if (requiredCount > 0 && selectedIds.length >= requiredCount) {
      setMessage("You have already selected the required number of questions. Remove one to add another.");
      return;
    }

    setSelectedIds([...selectedIds, questionId]);
  };

  const autoSelect = () => {
    if (!requiredCount || requiredCount <= 0) {
      setMessage("Enter the number of questions required.");
      return;
    }

    if (filteredQuestions.length < requiredCount) {
      setMessage("Not enough questions found for the selected filters. Please change filters or reduce question count.");
      return;
    }

    setSelectedIds(autoSelectFromQuestions(filteredQuestions, requiredCount, filters.difficulty).map(getQuestionId));
    setMessage("");
  };

  const generateLink = async () => {
    if (selectedExceedsLimit) {
      setMessage("Selected questions exceed the new limit. Please remove extra questions.");
      return;
    }

    if (hasGeneratedLink) {
      setMessage("Interview link has already been generated. Use Copy Link from the shortlisted candidates page.");
      return;
    }

    if (!canGenerate) {
      setMessage(`Selected ${selectedIds.length} / ${requiredCount}. Complete date, time, and selected questions before generating.`);
      return;
    }

    setSubmitting(true);
    setMessage("");
    setGeneratedLink("");

    try {
      const configureResponse = await fetch(`${API_BASE_URL}/api/interviews/${encodeURIComponent(applicationId)}/configure-questions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          number_of_questions: requiredCount,
          selected_question_ids: selectedIds,
          filters_used: filters,
        }),
      });
      const configureData = await configureResponse.json();

      if (!configureResponse.ok || !configureData.success) {
        throw new Error(configureData.detail || configureData.message || "Could not save selected questions.");
      }

      const linkResponse = await fetch(`${API_BASE_URL}/api/interview/create-link`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          application_id: applicationId,
          candidate_name: application?.candidate_name || "",
          email: application?.email || "",
          interview_date: interviewDate,
          interview_time: interviewTime,
          interview_scheduled_at: `${interviewDate}T${interviewTime}`,
        }),
      });
      const linkData = await linkResponse.json();

      if (!linkResponse.ok || !linkData.success) {
        throw new Error(linkData.detail || linkData.message || "Could not generate interview link.");
      }

      const link = linkData.verification_url || linkData.verificationUrl || linkData.link;
      setGeneratedLink(link);
      setApplication((current) => ({
        ...(current || {}),
        interview_link: link,
        interview_link_generated: true,
      }));
      navigator.clipboard?.writeText(link);
      setMessage(linkData.already_generated ? "Existing interview link copied." : "Interview link generated and copied.");
    } catch (error) {
      setMessage(error.message || "Could not generate interview link.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <main className="configure-page">
        <section className="configure-shell">
          <p>Loading interview configuration...</p>
        </section>
      </main>
    );
  }

  return (
    <main className="configure-page">
      <section className="configure-shell">
        <button className="back-button" type="button" onClick={onBack}>
          Back
        </button>

        <header className="configure-header">
          <div>
            <h1>Configure Interview</h1>
            <p>{application?.candidate_name || "Candidate"} | {application?.email || "No email"} | {application?.job_title || "Job"}</p>
          </div>
          <strong>Selected {selectedIds.length} / {requiredCount || 0}</strong>
        </header>

        <section className="configure-controls">
          <input type="date" value={interviewDate} disabled={hasGeneratedLink} onChange={(event) => setInterviewDate(event.target.value)} />
          <input type="time" value={interviewTime} disabled={hasGeneratedLink} onChange={(event) => setInterviewTime(event.target.value)} />
          <input
            type="number"
            min="1"
            placeholder="Number of Questions"
            value={questionCount}
            disabled={hasGeneratedLink}
            onChange={(event) => {
              setQuestionCount(event.target.value);
              setMessage("");
            }}
          />
        </section>

        {selectedExceedsLimit && <p className="configure-message">Selected questions exceed the new limit. Please remove extra questions.</p>}
        {!selectedExceedsLimit && selectedAtLimit && !hasGeneratedLink && (
          <p className="configure-message">You have already selected the required number of questions. Remove one to add another.</p>
        )}
        {hasGeneratedLink && <p className="configure-message">Interview link has already been generated. Selected questions and schedule are locked.</p>}
        {message && <p className="configure-message">{message}</p>}
        {generatedLink && <p className="generated-link">{generatedLink}</p>}

        <section className="configure-layout">
          <div className="question-browser">
            <div className="configure-filters">
              <input
                placeholder="Search questions, answers, tags, topics"
                value={filters.search}
                onChange={(event) => setFilters({ ...filters, search: event.target.value })}
              />
              <select value={filters.difficulty} onChange={(event) => setFilters({ ...filters, difficulty: event.target.value })}>
                <option value="all">All Difficulties</option>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
              <select value={filters.area_of_interest} onChange={(event) => setFilters({ ...filters, area_of_interest: event.target.value })}>
                <option value="all">All Areas</option>
                {areas.map((area) => (
                  <option value={area} key={area}>{area}</option>
                ))}
              </select>
              {jobRoles.length > 0 && (
                <select value={filters.job_role} onChange={(event) => setFilters({ ...filters, job_role: event.target.value })}>
                  <option value="all">All Job Roles</option>
                  {jobRoles.map((role) => (
                    <option value={role} key={role}>{role}</option>
                  ))}
                </select>
              )}
              <button className="report-button" type="button" onClick={autoSelect} disabled={hasGeneratedLink}>Auto Select</button>
            </div>

            <div className="question-results">
              {filteredQuestions.map((question) => {
                const questionId = getQuestionId(question);
                const selected = selectedIds.includes(questionId);
                const questionButtonDisabled = hasGeneratedLink || (!selected && (selectedAtLimit || requiredCount <= 0));

                return (
                  <article className="configure-question-card" key={questionId}>
                    <div>
                      <h3>{question.question}</h3>
                      <p>{question.expected_answer || question.expectedAnswer || "N/A"}</p>
                      <div className="configure-chip-row">
                        <span>{formatDifficulty(question.difficulty)}</span>
                        <span>{getQuestionArea(question)}</span>
                        {getQuestionTags(question).map((tag) => <span key={tag}>{tag}</span>)}
                      </div>
                    </div>
                    <button type="button" disabled={questionButtonDisabled} onClick={() => toggleQuestion(question)}>
                      {selected ? "Remove" : "Add"}
                    </button>
                  </article>
                );
              })}
              {!filteredQuestions.length && <p>Not enough questions found for the selected filters. Please change filters or reduce question count.</p>}
            </div>
          </div>

          <aside className="selected-cart">
            <h2>Selected Questions</h2>
            <p>Selected {selectedIds.length} / {requiredCount || 0}</p>
            {selectedQuestions.map((question, index) => (
              <article className="selected-cart-item" key={getQuestionId(question)}>
                <span>{index + 1}</span>
                <div>
                  <strong>{question.question}</strong>
                  <small>{formatDifficulty(question.difficulty)} | {getQuestionArea(question)}</small>
                </div>
                <button type="button" disabled={hasGeneratedLink} onClick={() => toggleQuestion(question)}>Remove</button>
              </article>
            ))}
            {!selectedQuestions.length && <p>No questions selected.</p>}
            {isInterviewLocked(application) && <p className="configure-message">This interview is already closed for link generation.</p>}
            <button className="generate-link-button" type="button" disabled={!canGenerate || submitting} onClick={generateLink}>
              {submitting ? "Generating..." : "Generate Interview Link"}
            </button>
          </aside>
        </section>
      </section>
    </main>
  );
}

export default ConfigureInterviewPage;


function getQuestionId(question) {
  return String(question?._id || question?.id || question?.question_id || "");
}


function getQuestionArea(question) {
  return question?.area_of_interest || question?.areaOfInterest || question?.category || "General";
}

function getQuestionTags(question) {
  if (Array.isArray(question?.tags)) {
    return question.tags;
  }

  return String(question?.tags || "")
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}


function isInterviewLocked(application) {
  const status = String(application?.interview_status || application?.interviewStatus || "").toLowerCase();

  return (
    application?.interview_completed === true ||
    application?.interviewCompleted === true ||
    ["completed", "partial", "quit"].includes(status)
  );
}


function normalizeDifficulty(value) {
  const difficulty = String(value || "medium").trim().toLowerCase();
  return ["easy", "medium", "hard"].includes(difficulty) ? difficulty : "medium";
}


function formatDifficulty(value) {
  const difficulty = normalizeDifficulty(value);
  return difficulty.charAt(0).toUpperCase() + difficulty.slice(1);
}


function getDateFromIso(value) {
  const text = String(value || "");
  return text.includes("T") ? text.split("T")[0] : "";
}


function getTimeFromIso(value) {
  const text = String(value || "");
  return text.includes("T") ? text.split("T")[1]?.slice(0, 5) || "" : "";
}


function autoSelectFromQuestions(questions, requestedCount, difficultyFilter) {
  if (difficultyFilter !== "all") {
    return questions.slice(0, requestedCount);
  }

  const buckets = {
    easy: questions.filter((question) => normalizeDifficulty(question.difficulty) === "easy"),
    medium: questions.filter((question) => normalizeDifficulty(question.difficulty) === "medium"),
    hard: questions.filter((question) => normalizeDifficulty(question.difficulty) === "hard"),
  };
  const plan = balancedDifficultyPlan(requestedCount);
  const selected = [];

  for (const difficulty of ["easy", "medium", "hard"]) {
    selected.push(...buckets[difficulty].splice(0, plan[difficulty]));
  }

  if (selected.length < requestedCount) {
    const selectedIds = new Set(selected.map(getQuestionId));
    selected.push(...questions.filter((question) => !selectedIds.has(getQuestionId(question))).slice(0, requestedCount - selected.length));
  }

  return selected.slice(0, requestedCount);
}


function balancedDifficultyPlan(count) {
  const plan = { easy: 0, medium: 0, hard: 0 };
  const order = ["easy", "medium", "hard", "easy", "medium"];

  for (let index = 0; index < count; index += 1) {
    plan[order[index % order.length]] += 1;
  }

  return plan;
}
