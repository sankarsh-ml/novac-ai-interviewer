export function fetchReport(reportRepository, applicationId) {
  return reportRepository.getReport(applicationId);
}

export const generateReport = fetchReport;
export const downloadReport = fetchReport;

export function fetchBulkReports(reportRepository, jobId, applicationIds) {
  return reportRepository.getBulkReports(jobId, applicationIds);
}
