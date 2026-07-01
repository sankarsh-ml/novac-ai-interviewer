import { apiRequest } from "../infrastructure/api/apiClient.js";
import { endpoints } from "../infrastructure/api/endpoints.js";

export function getCandidates(jobId) {
  return apiRequest(endpoints.jobApplications(jobId), { method: "GET" });
}

export function selectCandidate(applicationId) {
  return updateCandidateDecision(applicationId, "selected");
}

export function rejectCandidate(applicationId) {
  return updateCandidateDecision(applicationId, "rejected");
}

export function updateCandidateDecision(applicationId, decision) {
  return apiRequest(endpoints.applicationDecision(applicationId), {
    method: "PATCH",
    body: { decision },
  });
}

export function quickSelectCandidates(jobId, count) {
  return apiRequest(endpoints.quickSelect(jobId), {
    method: "POST",
    body: { count },
  });
}

export function deleteCandidate(applicationId) {
  return apiRequest(endpoints.application(applicationId), { method: "DELETE" });
}

export function deleteAllRecords(jobId) {
  return apiRequest(endpoints.jobRecords(jobId), { method: "DELETE" });
}
