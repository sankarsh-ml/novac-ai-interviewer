import { apiRequest } from "../infrastructure/api/apiClient.js";
import { endpoints } from "../infrastructure/api/endpoints.js";

export function getJobs() {
  return apiRequest(endpoints.jobs, { method: "GET" });
}

export function getJob(jobId) {
  return apiRequest(endpoints.job(jobId), { method: "GET" });
}

export function createJob(payload) {
  return apiRequest(endpoints.jobs, {
    method: "POST",
    body: payload,
  });
}

export function deleteJob(jobId) {
  return apiRequest(endpoints.job(jobId), { method: "DELETE" });
}
