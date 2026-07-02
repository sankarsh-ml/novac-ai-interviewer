export function fetchConfigureData(interviewRepository, applicationId) {
  return interviewRepository.getConfigureData(applicationId);
}

export function configureQuestions(interviewRepository, applicationId, payload) {
  return interviewRepository.configureQuestions(applicationId, payload);
}

export function createInterviewLink(interviewRepository, payload) {
  return interviewRepository.createInterviewLink(payload);
}

export function rescheduleInterviewLink(interviewRepository, payload) {
  return interviewRepository.rescheduleInterviewLink(payload);
}

export function fetchInterviewQuestions(interviewRepository, applicationId) {
  return interviewRepository.getInterviewQuestions(applicationId);
}

export function regenerateInterviewQuestions(interviewRepository, applicationId) {
  return interviewRepository.regenerateInterviewQuestions(applicationId);
}

export function transcribeInterviewAudio(interviewRepository, applicationId, audioBlob, filename) {
  return interviewRepository.transcribeInterviewAudio(applicationId, audioBlob, filename);
}

export function startInterview(interviewRepository, applicationId) {
  return interviewRepository.startInterview(applicationId);
}

export function checkInterviewAccess(interviewRepository, applicationId, attemptToken = "") {
  return interviewRepository.checkInterviewAccess(applicationId, attemptToken);
}

export function sendInterviewHeartbeat(interviewRepository, applicationId) {
  return interviewRepository.sendInterviewHeartbeat(applicationId);
}

export function quitInterview(interviewRepository, applicationId) {
  return interviewRepository.quitInterview(applicationId);
}

export function quitInterviewWithBeacon(interviewRepository, applicationId) {
  return interviewRepository.quitInterviewWithBeacon(applicationId);
}

export function evaluateInterviewAnswer(interviewRepository, applicationId, questionId, answerText, options) {
  return interviewRepository.evaluateInterviewAnswer(applicationId, questionId, answerText, options);
}

export const submitAnswer = evaluateInterviewAnswer;

export function completeInterview(interviewRepository, applicationId) {
  return interviewRepository.completeInterview(applicationId);
}

export const finishInterview = completeInterview;

export function saveInterviewAnswer(interviewRepository, applicationId, answer) {
  return interviewRepository.saveInterviewAnswer(applicationId, answer);
}

export function captureLivenessReference(interviewRepository, applicationId, payload) {
  return interviewRepository.captureLivenessReference(applicationId, payload);
}

export function checkLivenessFrame(interviewRepository, applicationId, payload) {
  return interviewRepository.checkLivenessFrame(applicationId, payload);
}

export function validateInterviewToken(interviewRepository, token) {
  return interviewRepository.validateInterviewToken(token);
}

export function requestCandidateToken(interviewRepository, token) {
  return interviewRepository.requestCandidateToken(token);
}

export function getQwenHealth(interviewRepository) {
  return interviewRepository.getQwenHealth();
}

export function verifyFaceFrame(interviewRepository, applicationId, blob) {
  return interviewRepository.verifyFaceFrame(applicationId, blob);
}
