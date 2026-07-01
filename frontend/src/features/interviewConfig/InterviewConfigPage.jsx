import { useEffect, useMemo, useState } from "react";
import IdentityConfigSelector from "../../components/interview/IdentityConfigSelector.jsx";
import InterviewTimerConfig from "../../components/interview/InterviewTimerConfig.jsx";
import ManualQuestionSelector from "../../components/interview/ManualQuestionSelector.jsx";
import QuestionSourceSelector from "../../components/interview/QuestionSourceSelector.jsx";
import QwenDifficultySplit from "../../components/interview/QwenDifficultySplit.jsx";
import { configureQuestions, createInterviewLink, getConfigureData } from "../../services/interviewApi.js";
import {
  getDefaultDifficultySplit,
  getDifficultySplitNumbers,
  validateDifficultySplit,
  validateTotalQuestionCount,
} from "../../domain/rules/questionRules.js";
import { isInterviewLocked, normalizeDifficultySplit, normalizeQuestionSource } from "../../domain/rules/interviewRules.js";
import { getDateFromIso, getTimeFromIso } from "../../domain/mappers/interviewMapper.js";
import "../../styles/ConfigureInterviewPage.css";

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
  const [questionSource, setQuestionSource] = useState("question_bank");
  const [questionBankCount, setQuestionBankCount] = useState(0);
  const [difficultySplit, setDifficultySplit] = useState({
    easy: "",
    medium: "",
    hard: "",
  });
  const [identityMode, setIdentityMode] = useState("government_id");
  const [resumePhotoAvailable, setResumePhotoAvailable] = useState(false);
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
      const data = await getConfigureData(applicationId);

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
      const loadedIdentityConfig = data.identityConfig || data.identity_config || data.interview_config?.identityConfig || data.application?.identityConfig || {};
      const hasResumePhoto = Boolean(
        loadedIdentityConfig.resumePhotoAvailable ??
        data.resumePhotoAvailable ??
        data.application?.resumePhotoAvailable
      );
      setResumePhotoAvailable(hasResumePhoto);
      setIdentityMode(
        hasResumePhoto && loadedIdentityConfig.requireGovernmentId === false
          ? "resume_photo"
          : "government_id"
      );
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

  const updateQuestionCount = (value) => {
    setQuestionCount(value);
    setMessage("");

    if (questionSource === "qwen_generated" && validateTotalQuestionCount(value) === "") {
      setDifficultySplit(getDefaultDifficultySplit(Number(value)));
    }
  };

  const generateLink = async () => {
    if (isQuestionBankMode && selectedExceedsLimit) {
      setMessage("Selected questions exceed the new limit. Please remove extra questions.");
      return;
    }

    if (hasGeneratedLink) {
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
      await configureQuestions(applicationId, {
        questionSource,
        questionCount: requiredCount,
        selectedQuestionIds: isQuestionBankMode ? selectedIds : [],
        difficultySplit: isQwenMode ? qwenSplit : null,
        identityConfig: {
          requireGovernmentId: identityMode !== "resume_photo",
          faceVerificationSource: identityMode === "resume_photo" ? "resume_photo" : "government_id",
        },
        filters_used: filters,
      });
      const linkData = await createInterviewLink({
        application_id: applicationId,
        candidate_name: application?.candidate_name || "",
        email: application?.email || "",
        interview_date: interviewDate,
        interview_time: interviewTime,
        interview_scheduled_at: `${interviewDate}T${interviewTime}`,
      });

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
      if (error.status === 503) {
        const fallbackMessage = questionBankCount === 0
          ? "Question bank is empty and Qwen generation failed. Please add questions to the bank or try again."
          : "Qwen question generation failed. Please try again or use question bank selection.";
        setMessage(fallbackMessage);
        return;
      }

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

        <InterviewTimerConfig
          interviewDate={interviewDate}
          interviewTime={interviewTime}
          questionCount={questionCount}
          isQwenMode={isQwenMode}
          disabled={hasGeneratedLink}
          onDateChange={setInterviewDate}
          onTimeChange={setInterviewTime}
          onQuestionCountChange={updateQuestionCount}
        />

        <IdentityConfigSelector
          identityMode={identityMode}
          resumePhotoAvailable={resumePhotoAvailable}
          hasGeneratedLink={hasGeneratedLink}
          onChange={setIdentityMode}
        />

        <QuestionSourceSelector
          isQuestionBankMode={isQuestionBankMode}
          isQwenMode={isQwenMode}
          questionBankCount={questionBankCount}
          hasGeneratedLink={hasGeneratedLink}
          onSelectQuestionBank={() => {
            setQuestionSource("question_bank");
            setMessage("");
          }}
          onSelectQwen={() => {
            setQuestionSource("qwen_generated");
            setSelectedIds([]);
            if (hasValidTotalQuestions) {
              setDifficultySplit(getDefaultDifficultySplit(requiredCount));
            }
            setMessage("");
          }}
        />

        {questionBankCount === 0 && (
          <p className="configure-message">No questions are available in the question bank. Qwen generation has been selected automatically.</p>
        )}

        {isQwenMode && (
          <QwenDifficultySplit
            hasValidTotalQuestions={hasValidTotalQuestions}
            difficultySplit={difficultySplit}
            total={qwenSplitTotal}
            disabled={hasGeneratedLink}
            onChange={setDifficultySplit}
          />
        )}

        {isQuestionBankMode && selectedExceedsLimit && <p className="configure-message">Selected questions exceed the new limit. Please remove extra questions.</p>}
        {isQuestionBankMode && !selectedExceedsLimit && selectedAtLimit && !hasGeneratedLink && (
          <p className="configure-message">You have already selected the required number of questions. Remove one to add another.</p>
        )}
        {hasGeneratedLink && <p className="configure-message">Interview link has already been generated. Selected questions and schedule are locked.</p>}
        {message && <p className="configure-message">{message}</p>}
        {generatedLink && <p className="generated-link">{generatedLink}</p>}

        <section className="configure-layout">
          {isQuestionBankMode && (
          <ManualQuestionSelector>
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
          </ManualQuestionSelector>
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
                <button type="button" disabled={hasGeneratedLink} onClick={() => toggleQuestion(question)}>Remove</button>
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


function normalizeDifficulty(value) {
  const difficulty = String(value || "medium").trim().toLowerCase();
  return ["easy", "medium", "hard"].includes(difficulty) ? difficulty : "medium";
}


function formatDifficulty(value) {
  const difficulty = normalizeDifficulty(value);
  return difficulty.charAt(0).toUpperCase() + difficulty.slice(1);
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
