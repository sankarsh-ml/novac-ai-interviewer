import { getAppConfig } from "./configLoader.js";

const endpointConfig = getAppConfig().api.endpoints;

function fillTemplate(template, params = {}) {
  return template.replace(/\{([^}]+)\}/g, (_, key) => encodeURIComponent(params[key] ?? ""));
}

export const endpoints = {
  adminLogin: endpointConfig.adminLogin,
  jobs: endpointConfig.jobs,
  job: (jobId) => fillTemplate(endpointConfig.job, { jobId }),
  jobApplications: (jobId) => fillTemplate(endpointConfig.jobApplications, { jobId }),
  jobRecords: (jobId) => fillTemplate(endpointConfig.jobRecords, { jobId }),
  quickSelect: (jobId) => fillTemplate(endpointConfig.quickSelect, { jobId }),
  application: (applicationId) => fillTemplate(endpointConfig.application, { applicationId }),
  applicationDecision: (applicationId) => fillTemplate(endpointConfig.applicationDecision, { applicationId }),
  resumeUpload: endpointConfig.resumeUpload,
  resumeBulkUpload: endpointConfig.resumeBulkUpload,
  resumeDownload: (applicationId) => fillTemplate(endpointConfig.resumeDownload, { applicationId }),
  resumeView: (applicationId) => fillTemplate(endpointConfig.resumeView, { applicationId }),
  atsScore: (applicationId) => fillTemplate(endpointConfig.atsScore, { applicationId }),
  atsDecision: (applicationId) => fillTemplate(endpointConfig.atsDecision, { applicationId }),
  questionBank: (jobId) => fillTemplate(endpointConfig.questionBank, { jobId }),
  questionBankSave: endpointConfig.questionBankSave,
  questionBankParseUpload: endpointConfig.questionBankParseUpload,
  questionBankQuestion: (questionId) => fillTemplate(endpointConfig.questionBankQuestion, { questionId }),
  questionBankClear: (jobId) => fillTemplate(endpointConfig.questionBankClear, { jobId }),
  configureData: (applicationId) => fillTemplate(endpointConfig.configureData, { applicationId }),
  configureQuestions: (applicationId) => fillTemplate(endpointConfig.configureQuestions, { applicationId }),
  createInterviewLink: endpointConfig.createInterviewLink,
  rescheduleInterviewLink: endpointConfig.rescheduleInterviewLink,
  interviewAccess: (applicationId) => fillTemplate(endpointConfig.interviewAccess, { applicationId }),
  interviewHeartbeat: (applicationId) => fillTemplate(endpointConfig.interviewHeartbeat, { applicationId }),
  interviewQuit: (applicationId) => fillTemplate(endpointConfig.interviewQuit, { applicationId }),
  interviewQuestions: (applicationId) => fillTemplate(endpointConfig.interviewQuestions, { applicationId }),
  interviewRegenerate: (applicationId) => fillTemplate(endpointConfig.interviewRegenerate, { applicationId }),
  interviewTranscribe: (applicationId) => fillTemplate(endpointConfig.interviewTranscribe, { applicationId }),
  interviewStart: (applicationId) => fillTemplate(endpointConfig.interviewStart, { applicationId }),
  interviewEvaluate: (applicationId) => fillTemplate(endpointConfig.interviewEvaluate, { applicationId }),
  interviewComplete: (applicationId) => fillTemplate(endpointConfig.interviewComplete, { applicationId }),
  interviewSaveAnswer: (applicationId) => fillTemplate(endpointConfig.interviewSaveAnswer, { applicationId }),
  livenessReference: (applicationId) => fillTemplate(endpointConfig.livenessReference, { applicationId }),
  livenessCheck: (applicationId) => fillTemplate(endpointConfig.livenessCheck, { applicationId }),
  interviewToken: (token) => fillTemplate(endpointConfig.interviewToken, { token }),
  qwenHealth: endpointConfig.qwenHealth,
  faceVerify: (applicationId) => fillTemplate(endpointConfig.faceVerify, { applicationId }),
  identityUpload: (applicationId) => fillTemplate(endpointConfig.identityUpload, { applicationId }),
  candidateVerification: (applicationId) => fillTemplate(endpointConfig.candidateVerification, { applicationId }),
  verificationStatus: (applicationId) => fillTemplate(endpointConfig.verificationStatus, { applicationId }),
  markVerified: (applicationId) => fillTemplate(endpointConfig.markVerified, { applicationId }),
  candidateReport: (applicationId) => fillTemplate(endpointConfig.candidateReport, { applicationId }),
  reports: endpointConfig.reports,
};
