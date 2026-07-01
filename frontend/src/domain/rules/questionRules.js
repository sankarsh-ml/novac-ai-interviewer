export function validateQuestionSource(source, questionBankCount = 0) {
  const normalized = String(source || "").toLowerCase();

  if (!["question_bank", "qwen_generated"].includes(normalized)) {
    return "Select a question source.";
  }

  if (normalized === "question_bank" && Number(questionBankCount) <= 0) {
    return "Question bank is empty. Use Qwen generated questions.";
  }

  return "";
}

export function validateTotalQuestionCount(value) {
  const text = String(value ?? "").trim();

  if (!text || !/^\d+$/.test(text) || Number(text) <= 0) {
    return "Total Questions must be a positive integer.";
  }

  return "";
}

export function validateDifficultySplit(split, totalQuestionCount) {
  const values = [split?.easy, split?.medium, split?.hard];

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

export function getDefaultDifficultySplit(total) {
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

export function canSelectQuestion(currentCount, maxCount) {
  const current = Number(currentCount);
  const max = Number(maxCount);
  return max > 0 && current < max;
}

export function getDifficultySplitNumbers(split) {
  return {
    easy: parseWholeNumber(split?.easy),
    medium: parseWholeNumber(split?.medium),
    hard: parseWholeNumber(split?.hard),
  };
}

export function normalizeDifficulty(value) {
  const difficulty = String(value || "medium").trim().toLowerCase();
  return ["easy", "medium", "hard"].includes(difficulty) ? difficulty : "medium";
}

export function formatDifficulty(value) {
  const difficulty = normalizeDifficulty(value);
  return difficulty.charAt(0).toUpperCase() + difficulty.slice(1);
}

export function splitTags(value) {
  if (Array.isArray(value)) {
    return value;
  }

  return String(value || "")
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
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
