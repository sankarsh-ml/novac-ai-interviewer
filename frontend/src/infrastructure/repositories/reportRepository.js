import { apiRequest } from "../api/apiClient.js";
import { endpoints } from "../config/endpoints.js";

export function getReport(applicationId) {
  return apiRequest(endpoints.candidateReport(applicationId), {
    method: "GET",
    responseType: "blob",
  });
}

export const generateReport = getReport;
export const downloadReport = getReport;

export function getBulkReports(jobId, applicationIds) {
  return apiRequest(endpoints.reports, {
    method: "POST",
    body: {
      application_ids: applicationIds,
      job_id: jobId,
    },
    responseType: "blob",
  });
}
