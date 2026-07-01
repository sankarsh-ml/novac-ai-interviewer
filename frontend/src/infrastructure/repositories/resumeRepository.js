import { buildApiUrl, apiRequest } from "../api/apiClient.js";
import { endpoints } from "../config/endpoints.js";

export async function uploadResume(file, jobId = "") {
  const formData = new FormData();
  formData.append("file", file);

  if (jobId) {
    formData.append("job_id", jobId);
  }

  return apiRequest(endpoints.resumeUpload, {
    method: "POST",
    body: formData,
  });
}

export function uploadBulkResumes(jobId, files) {
  const formData = new FormData();
  formData.append("job_id", jobId);
  files.forEach((file) => formData.append("resumes", file));

  return apiRequest(endpoints.resumeBulkUpload, {
    method: "POST",
    body: formData,
  });
}

export function submitAtsDecision(applicationId, decision) {
  return apiRequest(endpoints.atsDecision(applicationId), {
    method: "POST",
    body: { decision },
  });
}

export function scoreResume(applicationId) {
  return apiRequest(endpoints.atsScore(applicationId), { method: "GET" });
}

export function getResumeDownloadUrl(applicationId) {
  return buildApiUrl(endpoints.resumeDownload(applicationId));
}

export function getResumeViewUrl(applicationId) {
  return buildApiUrl(endpoints.resumeView(applicationId));
}

export const getResume = getResumeDownloadUrl;
export const viewResume = getResumeViewUrl;
