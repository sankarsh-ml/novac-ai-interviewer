import { apiRequest } from "../api/apiClient.js";
import { endpoints } from "../config/endpoints.js";

export function getJobs() {
  return apiRequest(endpoints.jobs, { auth: "admin", method: "GET" });
}

export function getJob(jobId) {
  return apiRequest(endpoints.job(jobId), { auth: "admin", method: "GET" });
}

export function createJob(payload) {
  return apiRequest(endpoints.jobs, {
    auth: "admin",
    method: "POST",
    body: payload,
  });
}

export function deleteJob(jobId) {
  return apiRequest(endpoints.job(jobId), { auth: "admin", method: "DELETE" });
}
