export function fetchQuestionBank(questionBankRepository, jobId) {
  return questionBankRepository.getQuestionBank(jobId);
}

export function saveQuestionBank(questionBankRepository, jobId, questions) {
  return questionBankRepository.saveQuestionBank(jobId, questions);
}

export function uploadQuestionBank(questionBankRepository, jobId, file) {
  return questionBankRepository.uploadQuestionBank(jobId, file);
}

export function updateQuestion(questionBankRepository, questionId, payload) {
  return questionBankRepository.updateQuestion(questionId, payload);
}

export function deleteQuestion(questionBankRepository, questionId, jobId) {
  return questionBankRepository.deleteQuestion(questionId, jobId);
}

export function clearQuestionBank(questionBankRepository, jobId) {
  return questionBankRepository.clearQuestionBank(jobId);
}

export function filterQuestionBank(questionBankRepository, questions, filters) {
  return questionBankRepository.filterQuestionBank(questions, filters);
}
