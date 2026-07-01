import { normalizeDifficulty, splitTags } from "../rules/questionRules.js";

export function normalizeQuestion(question) {
  return {
    ...question,
    question: question?.question || "",
    expected_answer: question?.expected_answer || question?.expectedAnswer || "N/A",
    difficulty: normalizeDifficulty(question?.difficulty),
    area_of_interest: question?.area_of_interest || question?.areaOfInterest || question?.category || "General",
    tags: splitTags(question?.tags),
    job_role: question?.job_role || question?.jobRole || "",
    score_weight: Number(question?.score_weight) || 1,
  };
}
