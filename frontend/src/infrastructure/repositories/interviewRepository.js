import { apiBeacon, apiRequest } from "../api/apiClient.js";
import { endpoints } from "../config/endpoints.js";

function cleanApplicationId(applicationId) {
  const value = String(applicationId || "").trim();
  if (!value) {
    throw new Error("Application ID missing. Please upload resume again.");
  }
  return value;
}

export function getConfigureData(applicationId) {
  return apiRequest(endpoints.configureData(cleanApplicationId(applicationId)), { auth: "admin", method: "GET" });
}

export function configureQuestions(applicationId, payload) {
  return apiRequest(endpoints.configureQuestions(cleanApplicationId(applicationId)), {
    auth: "admin",
    method: "POST",
    body: payload,
  });
}

export function createInterviewLink(payload) {
  return apiRequest(endpoints.createInterviewLink, {
    auth: "admin",
    method: "POST",
    body: payload,
  });
}

export function rescheduleInterviewLink(payload) {
  return apiRequest(endpoints.rescheduleInterviewLink, {
    auth: "admin",
    method: "POST",
    body: payload,
  });
}

export function getInterviewConfig(applicationId) {
  return getConfigureData(applicationId);
}

export function getInterviewQuestions(applicationId) {
  return apiRequest(endpoints.interviewQuestions(cleanApplicationId(applicationId)), { auth: "candidate", method: "GET" });
}

export function regenerateInterviewQuestions(applicationId) {
  return apiRequest(endpoints.interviewRegenerate(cleanApplicationId(applicationId)), { auth: "admin", method: "POST" });
}

export function transcribeInterviewAudio(applicationId, audioBlob, filename = "answer.webm") {
  if (!audioBlob || audioBlob.size === 0) {
    throw new Error("No recorded audio was found.");
  }

  const formData = new FormData();
  formData.append("audio", audioBlob, filename);

  return apiRequest(endpoints.interviewTranscribe(cleanApplicationId(applicationId)), {
    auth: "candidate",
    method: "POST",
    body: formData,
  });
}

export function startInterview(applicationId) {
  return apiRequest(endpoints.interviewStart(cleanApplicationId(applicationId)), { auth: "candidate", method: "POST" });
}

export function checkInterviewAccess(applicationId, attemptToken = "") {
  const query = attemptToken ? `?attempt=${encodeURIComponent(attemptToken)}` : "";
  return apiRequest(`${endpoints.interviewAccess(cleanApplicationId(applicationId))}${query}`, { auth: "none", method: "GET" });
}

export function sendInterviewHeartbeat(applicationId) {
  return apiRequest(endpoints.interviewHeartbeat(cleanApplicationId(applicationId)), { auth: "candidate", method: "POST" });
}

export function quitInterview(applicationId) {
  return apiRequest(endpoints.interviewQuit(cleanApplicationId(applicationId)), { auth: "candidate", method: "POST" });
}

export function quitInterviewWithBeacon(applicationId) {
  const value = String(applicationId || "").trim();
  return value ? apiBeacon(endpoints.interviewQuit(value), undefined, { auth: "candidate" }) : false;
}

export function evaluateInterviewAnswer(applicationId, questionId, answerText, options = {}) {
  if (!questionId) {
    throw new Error("Question ID missing.");
  }

  if (!String(answerText || "").trim()) {
    throw new Error("Please record an answer before submitting.");
  }

  return apiRequest(endpoints.interviewEvaluate(cleanApplicationId(applicationId)), {
    auth: "candidate",
    method: "POST",
    body: {
      question_id: questionId,
      answer_text: answerText,
      transcript: options.transcript || "",
      audio_path: options.audioPath || "",
    },
  });
}

export const submitAnswer = evaluateInterviewAnswer;

export function completeInterview(applicationId) {
  return apiRequest(endpoints.interviewComplete(cleanApplicationId(applicationId)), { auth: "candidate", method: "POST" });
}

export const finishInterview = completeInterview;

export function saveInterviewAnswer(applicationId, answer) {
  return apiRequest(endpoints.interviewSaveAnswer(cleanApplicationId(applicationId)), {
    auth: "candidate",
    method: "POST",
    body: answer || {},
  });
}

export function captureLivenessReference(applicationId, payload) {
  return apiRequest(endpoints.livenessReference(cleanApplicationId(applicationId)), {
    auth: "candidate",
    method: "POST",
    body: payload || {},
  });
}

export function checkLivenessFrame(applicationId, payload) {
  return apiRequest(endpoints.livenessCheck(cleanApplicationId(applicationId)), {
    auth: "candidate",
    method: "POST",
    body: payload || {},
  });
}

export function validateInterviewToken(token) {
  const cleanToken = String(token || "").trim();
  if (!cleanToken) {
    throw new Error("Interview token missing.");
  }
  return apiRequest(endpoints.interviewToken(cleanToken), { auth: "none", method: "GET" });
}

export function requestCandidateToken(interviewLinkToken) {
  const cleanToken = String(interviewLinkToken || "").trim();
  if (!cleanToken) {
    throw new Error("Interview token missing.");
  }
  return apiRequest(endpoints.candidateToken, {
    auth: "none",
    method: "POST",
    body: { interviewLinkToken: cleanToken },
  });
}

export function getQwenHealth() {
  return apiRequest(endpoints.qwenHealth, { auth: "none", method: "GET" });
}

export function verifyFaceFrame(applicationId, blob) {
  if (!blob) {
    throw new Error("Live webcam frame is missing.");
  }

  const formData = new FormData();
  formData.append("frame", blob, "live-frame.jpg");

  return apiRequest(endpoints.faceVerify(cleanApplicationId(applicationId)), {
    auth: "candidate",
    method: "POST",
    body: formData,
  });
}

export function getInterviewResult(applicationId) {
  return getInterviewQuestions(applicationId);
}
