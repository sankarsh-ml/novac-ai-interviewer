export function uploadResume(resumeRepository, file, jobId) {
  return resumeRepository.uploadResume(file, jobId);
}

export function uploadBulkResumes(resumeRepository, jobId, files) {
  return resumeRepository.uploadBulkResumes(jobId, files);
}

export function submitAtsDecision(resumeRepository, applicationId, decision) {
  return resumeRepository.submitAtsDecision(applicationId, decision);
}

export function scoreResume(resumeRepository, applicationId) {
  return resumeRepository.scoreResume(applicationId);
}

export function getResumeDownloadUrl(resumeRepository, applicationId) {
  return resumeRepository.getResumeDownloadUrl(applicationId);
}

export function getResumeViewUrl(resumeRepository, applicationId) {
  return resumeRepository.getResumeViewUrl(applicationId);
}
