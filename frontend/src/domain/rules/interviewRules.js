export function shouldUseQwenMode(questionBankCount) {
  return Number(questionBankCount) <= 0;
}

export function canGenerateInterviewLink(config) {
  return Boolean(
    config?.interviewDate &&
      config?.interviewTime &&
      Number(config?.questionCount) > 0 &&
      !config?.isInterviewLocked &&
      !config?.hasGeneratedLink
  );
}

export function normalizeInterviewConfig(config = {}) {
  return {
    questionSource: normalizeQuestionSource(config.question_source || config.questionSource),
    numberOfQuestions: config.number_of_questions || config.numberOfQuestions || "",
    selectedQuestionIds: config.selected_question_ids || config.selectedQuestionIds || [],
    difficultySplit: normalizeDifficultySplit(config.difficulty_split || config.difficultySplit),
  };
}

export function normalizeQuestionSource(value) {
  return String(value || "question_bank").toLowerCase() === "qwen_generated" ? "qwen_generated" : "question_bank";
}

export function normalizeDifficultySplit(value) {
  const split = value && typeof value === "object" ? value : {};

  return {
    easy: split.easy ?? "",
    medium: split.medium ?? "",
    hard: split.hard ?? "",
  };
}

export function isInterviewLocked(application) {
  const status = String(application?.interview_status || application?.interviewStatus || "").toLowerCase();

  return (
    application?.interview_completed === true ||
    application?.interviewCompleted === true ||
    ["complete", "completed", "partial"].includes(status)
  );
}
