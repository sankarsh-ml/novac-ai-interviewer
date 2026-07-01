import { apiRequest } from "../infrastructure/api/apiClient.js";
import { endpoints } from "../infrastructure/api/endpoints.js";

export function getQuestionBank(jobId) {
  return apiRequest(endpoints.questionBank(jobId), { method: "GET" });
}

export function saveQuestionBank(jobId, questions) {
  return apiRequest(endpoints.questionBankSave, {
    method: "POST",
    body: { job_id: jobId, questions },
  });
}

export function uploadQuestionBank(jobId, file) {
  const formData = new FormData();
  formData.append("job_id", jobId);
  formData.append("file", file);

  return apiRequest(endpoints.questionBankParseUpload, {
    method: "POST",
    body: formData,
  });
}

export function updateQuestion(questionId, payload) {
  return apiRequest(endpoints.questionBankQuestion(questionId), {
    method: "PUT",
    body: payload,
  });
}

export function deleteQuestion(questionId, jobId) {
  return apiRequest(`${endpoints.questionBankQuestion(questionId)}?job_id=${encodeURIComponent(jobId)}`, {
    method: "DELETE",
  });
}

export function clearQuestionBank(jobId) {
  return apiRequest(endpoints.questionBankClear(jobId), { method: "DELETE" });
}

export function filterQuestionBank(questions, filters) {
  const { difficulty = "all", area = "all", jobRole = "all", search = "" } = filters || {};
  const normalizedSearch = search.trim().toLowerCase();

  return (questions || []).filter((item) => {
    const itemDifficulty = normalizeDifficulty(item.difficulty);
    const itemArea = item.area_of_interest || item.areaOfInterest || item.category || "General";
    const itemJobRole = item.job_role || item.jobRole || "";
    const tags = Array.isArray(item.tags) ? item.tags.join(" ") : String(item.tags || "");
    const haystack = [
      item.question,
      item.expected_answer || item.expectedAnswer,
      itemArea,
      tags,
      itemJobRole,
    ].join(" ").toLowerCase();

    return (
      (difficulty === "all" || itemDifficulty === difficulty) &&
      (area === "all" || itemArea === area) &&
      (jobRole === "all" || itemJobRole === jobRole) &&
      (!normalizedSearch || haystack.includes(normalizedSearch))
    );
  });
}

function normalizeDifficulty(value) {
  const difficulty = String(value || "medium").trim().toLowerCase();
  return ["easy", "medium", "hard"].includes(difficulty) ? difficulty : "medium";
}
