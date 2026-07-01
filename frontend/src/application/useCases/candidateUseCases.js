export function fetchCandidates(candidateRepository, jobId) {
  return candidateRepository.getCandidates(jobId);
}

export function selectCandidate(candidateRepository, applicationId) {
  return candidateRepository.selectCandidate(applicationId);
}

export function rejectCandidate(candidateRepository, applicationId) {
  return candidateRepository.rejectCandidate(applicationId);
}

export function updateCandidateDecision(candidateRepository, applicationId, decision) {
  return candidateRepository.updateCandidateDecision(applicationId, decision);
}

export function quickSelectCandidates(candidateRepository, jobId, count) {
  return candidateRepository.quickSelectCandidates(jobId, count);
}

export function deleteCandidate(candidateRepository, applicationId) {
  return candidateRepository.deleteCandidate(applicationId);
}

export function deleteAllRecords(candidateRepository, jobId) {
  return candidateRepository.deleteAllRecords(jobId);
}
