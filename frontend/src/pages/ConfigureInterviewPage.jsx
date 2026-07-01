import { useEffect, useMemo, useState } from "react";
import "../styles/ConfigureInterviewPage.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function ConfigureInterviewPage({applicationId,onBack,mode = "generate",}) {
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
  const [questionSource, setQuestionSource] = useState("question_bank");
  const [questionBankCount, setQuestionBankCount] = useState(0);
  const [difficultySplit, setDifficultySplit] = useState({
    easy: "",
    medium: "",
    hard: "",
  });
  const [selectedIds, setSelectedIds] = useState([]);
  const [message, setMessage] = useState("");
  const [generatedLink, setGeneratedLink] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const isReschedule = mode === "reschedule";
  console.log("MODE =", mode);
  console.log("IS RESCHEDULE =", isReschedule);
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
      const loadedQuestions = Array.isArray(data.questions) ? data.questions : [];
      const totalQuestionBankCount = Number(data.question_bank_count ?? loadedQuestions.length);
      const configuredSource = normalizeQuestionSource(data.interview_config?.question_source || data.default_question_source);
      setQuestions(loadedQuestions);
      setQuestionBankCount(totalQuestionBankCount);
      setInterviewDate(data.application?.interview_date || getDateFromIso(data.application?.interview_scheduled_at) || "");
      setInterviewTime(data.application?.interview_time || getTimeFromIso(data.application?.interview_scheduled_at) || "");
      setQuestionCount(data.interview_config?.number_of_questions || "");
      setSelectedIds(data.interview_config?.selected_question_ids || []);
      setQuestionSource(totalQuestionBankCount === 0 ? "qwen_generated" : configuredSource);
      setDifficultySplit(normalizeDifficultySplit(data.interview_config?.difficulty_split));
      setGeneratedLink(data.application?.interview_link || "");
      if (totalQuestionBankCount === 0) {
        setMessage("No questions are available in the question bank. Qwen generation has been selected automatically.");
      }
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
  const totalQuestionValidation = validateTotalQuestionCount(questionCount);
  const hasValidTotalQuestions = !totalQuestionValidation;
  const requiredCount = hasValidTotalQuestions ? Number(questionCount) : 0;
  const qwenSplit = getDifficultySplitNumbers(difficultySplit);
  const qwenSplitTotal = qwenSplit.easy + qwenSplit.medium + qwenSplit.hard;
  const isQwenMode = questionSource === "qwen_generated";
  const isQuestionBankMode = questionSource === "question_bank";
  const hasGeneratedLink = Boolean(
    application?.interview_link_generated ||
    application?.interview_link ||
    generatedLink
  );
  const selectedExceedsLimit = requiredCount > 0 && selectedIds.length > requiredCount;
  const selectedAtLimit = requiredCount > 0 && selectedIds.length >= requiredCount;
  const qwenSplitMatchesCount = qwenSplitTotal === requiredCount;
  const canGenerate =
    Boolean(interviewDate) &&
    Boolean(interviewTime) &&
    requiredCount > 0 &&
    (isQwenMode ? qwenSplitTotal > 0 && qwenSplitMatchesCount : selectedIds.length === requiredCount) &&
    !isInterviewLocked(application) &&
    (isReschedule || !hasGeneratedLink);

  const toggleQuestion = (question) => {
    const questionId = getQuestionId(question);

    if (!questionId) {
      return;
    }

    if (selectedIds.includes(questionId)) {
      if (hasGeneratedLink && !isReschedule) {
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

  const updateQuestionCount = (value) => {
    setQuestionCount(value);
    setMessage("");

    if (questionSource === "qwen_generated" && validateTotalQuestionCount(value) === "") {
      setDifficultySplit(buildDefaultDifficultySplit(Number(value)));
    }
  };

  const generateLink = async () => {
    console.log("Generate called");
    console.log("MODE =", mode);
    console.log("IS RESCHEDULE =", isReschedule);
    if (isQuestionBankMode && selectedExceedsLimit) {
      setMessage("Selected questions exceed the new limit. Please remove extra questions.");
      return;
    }

    if (hasGeneratedLink && !isReschedule) {
      setMessage("Interview link has already been generated. Use Copy Link from the shortlisted candidates page.");
      return;
    }

    if (isQwenMode) {
      if (totalQuestionValidation) {
        setMessage(totalQuestionValidation);
        return;
      }

      const splitValidation = validateDifficultySplit(difficultySplit, requiredCount);

      if (splitValidation) {
        setMessage(splitValidation);
        return;
      }
    }

    if (!canGenerate) {
      if (isQwenMode) {
        setMessage("Complete date, time, and Qwen difficulty split before generating.");
        return;
      }

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
          questionSource,
          questionCount: requiredCount,
          selectedQuestionIds: isQuestionBankMode ? selectedIds : [],
          difficultySplit: isQwenMode ? qwenSplit : null,
          filters_used: filters,
          reschedule: isReschedule,
        }),
      });
      const configureData = await configureResponse.json();

      if (!configureResponse.ok || !configureData.success) {
        if (configureResponse.status === 503) {
          const fallbackMessage = questionBankCount === 0
            ? "Question bank is empty and Qwen generation failed. Please add questions to the bank or try again."
            : "Qwen question generation failed. Please try again or use question bank selection.";
          throw new Error(fallbackMessage);
        }

        throw new Error(configureData.detail || configureData.message || "Could not save selected questions.");
      }

      const endpoint = isReschedule? "reschedule-link": "create-link";
      console.log("Mode:", mode);
      console.log("Endpoint:", endpoint);
      const linkResponse = await fetch(`${API_BASE_URL}/api/interview/${endpoint}`, {
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
          <strong>{isQwenMode ? `Qwen ${qwenSplitTotal} / ${requiredCount || 0}` : `Selected ${selectedIds.length} / ${requiredCount || 0}`}</strong>
        </header>

        <section className="configure-controls">
          <input type="date" value={interviewDate} disabled={hasGeneratedLink && !isReschedule} onChange={(event) => setInterviewDate(event.target.value)} />
          <input type="time" value={interviewTime} disabled={hasGeneratedLink && !isReschedule} onChange={(event) => setInterviewTime(event.target.value)} />
          <input
            type="number"
            min="1"
            placeholder={isQwenMode ? "Total Questions" : "Number of Questions"}
            value={questionCount}
            disabled={hasGeneratedLink && !isReschedule}
            onChange={(event) => updateQuestionCount(event.target.value)}
          />
        </section>

        <section className="question-source-panel">
          <span>Question Source:</span>
          <div className="source-toggle" role="radiogroup" aria-label="Question Source">
            <label className={isQuestionBankMode ? "active" : ""}>
              <input
                type="radio"
                name="question-source"
                value="question_bank"
                checked={isQuestionBankMode}
                disabled={(hasGeneratedLink && !isReschedule) || questionBankCount === 0}
                onChange={() => {
                  setQuestionSource("question_bank");
                  setMessage("");
                }}
              />
              Select from Question Bank
            </label>
            <label className={isQwenMode ? "active" : ""}>
              <input
                type="radio"
                name="question-source"
                value="qwen_generated"
                checked={isQwenMode}
                disabled={hasGeneratedLink && !isReschedule}
                onChange={() => {
                  setQuestionSource("qwen_generated");
                  setSelectedIds([]);
                  if (hasValidTotalQuestions) {
                    setDifficultySplit(buildDefaultDifficultySplit(requiredCount));
                  }
                  setMessage("");
                }}
              />
              Generate with Qwen
            </label>
          </div>
        </section>

        {questionBankCount === 0 && (
          <p className="configure-message">No questions are available in the question bank. Qwen generation has been selected automatically.</p>
        )}

        {isQwenMode && (
          <section className="qwen-panel">
            <p>Qwen will generate interview questions automatically using the job description, required skills, and candidate resume/project details.</p>
            {!hasValidTotalQuestions && (
              <p className="qwen-step-note">Enter a valid Total Questions value to set the Easy, Medium, and Hard split.</p>
            )}
            {hasValidTotalQuestions && (
            <>
            <div className="qwen-split-grid">
              <label>
                Easy Questions
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={difficultySplit.easy}
                  disabled={hasGeneratedLink && !isReschedule}
                  onChange={(event) => setDifficultySplit({ ...difficultySplit, easy: event.target.value })}
                />
              </label>
              <label>
                Medium Questions
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={difficultySplit.medium}
                  disabled={hasGeneratedLink && !isReschedule}
                  onChange={(event) => setDifficultySplit({ ...difficultySplit, medium: event.target.value })}
                />
              </label>
              <label>
                Hard Questions
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={difficultySplit.hard}
                  disabled={hasGeneratedLink && !isReschedule}
                  onChange={(event) => setDifficultySplit({ ...difficultySplit, hard: event.target.value })}
                />
              </label>
            </div>
            <strong>Total Qwen Questions: {qwenSplitTotal}</strong>
            </>
            )}
          </section>
        )}

        {isQuestionBankMode && selectedExceedsLimit && <p className="configure-message">Selected questions exceed the new limit. Please remove extra questions.</p>}
        {isQuestionBankMode && !selectedExceedsLimit && selectedAtLimit && !hasGeneratedLink && (
          <p className="configure-message">You have already selected the required number of questions. Remove one to add another.</p>
        )}
        {hasGeneratedLink && !isReschedule && (<p className="configure-message">Interview link has already been generated. Selected questions and schedule are locked.</p>)}
        {message && <p className="configure-message">{message}</p>}
        {generatedLink && !isReschedule && (<p className="generated-link">{generatedLink}</p>)}

        <section className="configure-layout">
          {isQuestionBankMode && (
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
              <button className="report-button" type="button" onClick={autoSelect} disabled={hasGeneratedLink && !isReschedule}>Auto Select</button>
            </div>

            <div className="question-results">
              {filteredQuestions.map((question) => {
                const questionId = getQuestionId(question);
                const selected = selectedIds.includes(questionId);
                const questionButtonDisabled =(hasGeneratedLink && !isReschedule) || (!selected && (selectedAtLimit || requiredCount <= 0));

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
          )}

          <aside className="selected-cart">
            <h2>{isQwenMode ? "Qwen Questions" : "Selected Questions"}</h2>
            <p>{isQwenMode ? `Difficulty split ${qwenSplitTotal} / ${requiredCount || 0}` : `Selected ${selectedIds.length} / ${requiredCount || 0}`}</p>
            {isQwenMode && (
              <div className="qwen-summary">
                <span>Easy: {qwenSplit.easy}</span>
                <span>Medium: {qwenSplit.medium}</span>
                <span>Hard: {qwenSplit.hard}</span>
              </div>
            )}
            {isQuestionBankMode && (
            <>
            {selectedQuestions.map((question, index) => (
              <article className="selected-cart-item" key={getQuestionId(question)}>
                <span>{index + 1}</span>
                <div>
                  <strong>{question.question}</strong>
                  <small>{formatDifficulty(question.difficulty)} | {getQuestionArea(question)}</small>
                </div>
                <button type="button" disabled={hasGeneratedLink && !isReschedule} onClick={() => toggleQuestion(question)}>Remove</button>
              </article>
            ))}
            {!selectedQuestions.length && <p>No questions selected.</p>}
            </>
            )}
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
    ["completed","quit"].includes(status)
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


function normalizeQuestionSource(value) {
  return String(value || "question_bank").toLowerCase() === "qwen_generated" ? "qwen_generated" : "question_bank";
}


function normalizeDifficultySplit(value) {
  const split = value && typeof value === "object" ? value : {};

  return {
    easy: split.easy ?? "",
    medium: split.medium ?? "",
    hard: split.hard ?? "",
  };
}


function buildDefaultDifficultySplit(total) {
  const count = Number(total);

  if (count === 1) {
    return { easy: 1, medium: 0, hard: 0 };
  }

  if (count === 2) {
    return { easy: 1, medium: 1, hard: 0 };
  }

  if (count === 3) {
    return { easy: 1, medium: 1, hard: 1 };
  }

  if (count === 4) {
    return { easy: 1, medium: 2, hard: 1 };
  }

  if (count === 5) {
    return { easy: 2, medium: 2, hard: 1 };
  }

  const hard = Math.max(1, Math.round(count * 0.2));
  const remaining = count - hard;
  const easy = Math.floor(remaining / 2);
  const medium = count - hard - easy;

  return { easy, medium, hard };
}


function getDifficultySplitNumbers(split) {
  return {
    easy: parseWholeNumber(split.easy),
    medium: parseWholeNumber(split.medium),
    hard: parseWholeNumber(split.hard),
  };
}


function validateTotalQuestionCount(value) {
  const text = String(value ?? "").trim();

  if (!text) {
    return "Total Questions must be a positive integer.";
  }

  if (!/^\d+$/.test(text)) {
    return "Total Questions must be a positive integer.";
  }

  if (Number(text) <= 0) {
    return "Total Questions must be a positive integer.";
  }

  return "";
}


function parseWholeNumber(value) {
  const text = String(value ?? "").trim();

  if (!text) {
    return 0;
  }

  if (!/^\d+$/.test(text)) {
    return Number.NaN;
  }

  return Number(text);
}


function validateDifficultySplit(split, totalQuestionCount) {
  const values = [split.easy, split.medium, split.hard];

  if (values.some((value) => {
    const text = String(value ?? "").trim();
    return text && !/^\d+$/.test(text);
  })) {
    return "Difficulty split values must be whole numbers.";
  }

  const counts = getDifficultySplitNumbers(split);

  if ([counts.easy, counts.medium, counts.hard].some((value) => !Number.isInteger(value) || value < 0)) {
    return "Difficulty split values must be whole numbers.";
  }

  const total = counts.easy + counts.medium + counts.hard;

  if (total <= 0) {
    return "At least one question must be generated.";
  }

  if (totalQuestionCount > 0 && total > totalQuestionCount) {
    return "Difficulty split exceeds the maximum allowed question count.";
  }

  if (total !== totalQuestionCount) {
    return "Difficulty split must add up to the total number of interview questions.";
  }

  return "";
}
