import { apiRequest } from "../api/apiClient.js";
import { endpoints } from "../config/endpoints.js";

export function getCandidates(jobId) {
  return apiRequest(endpoints.jobApplications(jobId), { auth: "admin", method: "GET" });
}

export function selectCandidate(applicationId) {
  return updateCandidateDecision(applicationId, "selected");
}

export function rejectCandidate(applicationId) {
  return updateCandidateDecision(applicationId, "rejected");
}

export function updateCandidateDecision(applicationId, decision) {
  return apiRequest(endpoints.applicationDecision(applicationId), {
    auth: "admin",
    method: "PATCH",
    body: { decision },
  });
}

export function quickSelectCandidates(jobId, count) {
  return apiRequest(endpoints.quickSelect(jobId), {
    auth: "admin",
    method: "POST",
    body: { count },
  });
}

export function deleteCandidate(applicationId) {
  return apiRequest(endpoints.application(applicationId), { auth: "admin", method: "DELETE" });
}

export function deleteAllRecords(jobId) {
  return apiRequest(endpoints.jobRecords(jobId), { auth: "admin", method: "DELETE" });
}
