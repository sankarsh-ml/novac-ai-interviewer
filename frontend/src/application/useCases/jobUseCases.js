export function fetchJobs(jobRepository) {
  return jobRepository.getJobs();
}

export function fetchJob(jobRepository, jobId) {
  return jobRepository.getJob(jobId);
}

export function createJob(jobRepository, payload) {
  return jobRepository.createJob(payload);
}

export function deleteJob(jobRepository, jobId) {
  return jobRepository.deleteJob(jobId);
}
