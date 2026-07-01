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
  return apiRequest(endpoints.configureData(cleanApplicationId(applicationId)), { method: "GET" });
}

export function configureQuestions(applicationId, payload) {
  return apiRequest(endpoints.configureQuestions(cleanApplicationId(applicationId)), {
    method: "POST",
    body: payload,
  });
}

export function createInterviewLink(payload) {
  return apiRequest(endpoints.createInterviewLink, {
    method: "POST",
    body: payload,
  });
}

export function rescheduleInterviewLink(payload) {
  return apiRequest(endpoints.rescheduleInterviewLink, {
    method: "POST",
    body: payload,
  });
}

export function getInterviewConfig(applicationId) {
  return getConfigureData(applicationId);
}

export function getInterviewQuestions(applicationId) {
  return apiRequest(endpoints.interviewQuestions(cleanApplicationId(applicationId)), { method: "GET" });
}

export function regenerateInterviewQuestions(applicationId) {
  return apiRequest(endpoints.interviewRegenerate(cleanApplicationId(applicationId)), { method: "POST" });
}

export function transcribeInterviewAudio(applicationId, audioBlob, filename = "answer.webm") {
  if (!audioBlob || audioBlob.size === 0) {
    throw new Error("No recorded audio was found.");
  }

  const formData = new FormData();
  formData.append("audio", audioBlob, filename);

  return apiRequest(endpoints.interviewTranscribe(cleanApplicationId(applicationId)), {
    method: "POST",
    body: formData,
  });
}

export function startInterview(applicationId) {
  return apiRequest(endpoints.interviewStart(cleanApplicationId(applicationId)), { method: "POST" });
}

export function checkInterviewAccess(applicationId) {
  return apiRequest(endpoints.interviewAccess(cleanApplicationId(applicationId)), { method: "GET" });
}

export function sendInterviewHeartbeat(applicationId) {
  return apiRequest(endpoints.interviewHeartbeat(cleanApplicationId(applicationId)), { method: "POST" });
}

export function quitInterview(applicationId) {
  return apiRequest(endpoints.interviewQuit(cleanApplicationId(applicationId)), { method: "POST" });
}

export function quitInterviewWithBeacon(applicationId) {
  const value = String(applicationId || "").trim();
  return value ? apiBeacon(endpoints.interviewQuit(value)) : false;
}

export function evaluateInterviewAnswer(applicationId, questionId, answerText, options = {}) {
  if (!questionId) {
    throw new Error("Question ID missing.");
  }

  if (!String(answerText || "").trim()) {
    throw new Error("Please record an answer before submitting.");
  }

  return apiRequest(endpoints.interviewEvaluate(cleanApplicationId(applicationId)), {
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
  return apiRequest(endpoints.interviewComplete(cleanApplicationId(applicationId)), { method: "POST" });
}

export const finishInterview = completeInterview;

export function saveInterviewAnswer(applicationId, answer) {
  return apiRequest(endpoints.interviewSaveAnswer(cleanApplicationId(applicationId)), {
    method: "POST",
    body: answer || {},
  });
}

export function captureLivenessReference(applicationId, payload) {
  return apiRequest(endpoints.livenessReference(cleanApplicationId(applicationId)), {
    method: "POST",
    body: payload || {},
  });
}

export function checkLivenessFrame(applicationId, payload) {
  return apiRequest(endpoints.livenessCheck(cleanApplicationId(applicationId)), {
    method: "POST",
    body: payload || {},
  });
}

export function validateInterviewToken(token) {
  const cleanToken = String(token || "").trim();
  if (!cleanToken) {
    throw new Error("Interview token missing.");
  }
  return apiRequest(endpoints.interviewToken(cleanToken), { method: "GET" });
}

export function getQwenHealth() {
  return apiRequest(endpoints.qwenHealth, { method: "GET" });
}

export function verifyFaceFrame(applicationId, blob) {
  if (!blob) {
    throw new Error("Live webcam frame is missing.");
  }

  const formData = new FormData();
  formData.append("frame", blob, "live-frame.jpg");

  return apiRequest(endpoints.faceVerify(cleanApplicationId(applicationId)), {
    method: "POST",
    body: formData,
  });
}

export function getInterviewResult(applicationId) {
  return getInterviewQuestions(applicationId);
}
