import { apiRequest, buildAuthenticatedApiUrl } from "../api/apiClient.js";
import { endpoints } from "../config/endpoints.js";

export async function uploadResume(file, jobId = "") {
  const formData = new FormData();
  formData.append("file", file);

  if (jobId) {
    formData.append("job_id", jobId);
  }

  return apiRequest(endpoints.resumeUpload, {
    auth: "none",
    method: "POST",
    body: formData,
  });
}

export function uploadBulkResumes(jobId, files) {
  const formData = new FormData();
  formData.append("job_id", jobId);
  files.forEach((file) => formData.append("resumes", file));

  return apiRequest(endpoints.resumeBulkUpload, {
    auth: "admin",
    method: "POST",
    body: formData,
  });
}

export function submitAtsDecision(applicationId, decision) {
  return apiRequest(endpoints.atsDecision(applicationId), {
    auth: "admin",
    method: "POST",
    body: { decision },
  });
}

export function scoreResume(applicationId) {
  return apiRequest(endpoints.atsScore(applicationId), { auth: "admin", method: "GET" });
}

export function getResumeDownloadUrl(applicationId) {
  return buildAuthenticatedApiUrl(endpoints.resumeDownload(applicationId), "admin");
}

export function getResumeViewUrl(applicationId) {
  return buildAuthenticatedApiUrl(endpoints.resumeView(applicationId), "admin");
}

export const getResume = getResumeDownloadUrl;
export const viewResume = getResumeViewUrl;
