const API_BASE_URL = "http://127.0.0.1:8000";


export async function getInterviewQuestions(applicationId) {
  const cleanApplicationId = getCleanApplicationId(applicationId);
  return fetchInterviewJson(
    `${API_BASE_URL}/api/interview/${encodeURIComponent(cleanApplicationId)}/questions`,
    {
      method: "GET",
    },
    "Could not load interview questions."
  );
}


export async function regenerateInterviewQuestions(applicationId) {
  const cleanApplicationId = getCleanApplicationId(applicationId);
  return fetchInterviewJson(
    `${API_BASE_URL}/api/interview/questions/${encodeURIComponent(cleanApplicationId)}/regenerate`,
    {
      method: "POST",
    },
    "Could not regenerate interview questions."
  );
}


export async function transcribeInterviewAudio(applicationId, audioBlob, filename = "answer.webm") {
  const cleanApplicationId = getCleanApplicationId(applicationId);

  if (!audioBlob || audioBlob.size === 0) {
    throw new Error("No recorded audio was found.");
  }

  const formData = new FormData();
  formData.append("audio", audioBlob, filename);

  return fetchInterviewJson(
    `${API_BASE_URL}/api/interview/${encodeURIComponent(cleanApplicationId)}/transcribe`,
    {
      method: "POST",
      body: formData,
    },
    "Could not transcribe audio."
  );
}


export async function startInterview(applicationId) {
  const cleanApplicationId = getCleanApplicationId(applicationId);
  return fetchInterviewJson(
    `${API_BASE_URL}/api/interview/${encodeURIComponent(cleanApplicationId)}/start`,
    {
      method: "POST",
    },
    "Could not start interview."
  );
}


export async function checkInterviewAccess(applicationId) {
  const cleanApplicationId = getCleanApplicationId(applicationId);
  return fetchInterviewJson(
    `${API_BASE_URL}/api/interviews/${encodeURIComponent(cleanApplicationId)}/access-status`,
    {
      method: "GET",
    },
    "Could not check interview schedule."
  );
}


export async function sendInterviewHeartbeat(applicationId) {
  const cleanApplicationId = getCleanApplicationId(applicationId);
  return fetchInterviewJson(
    `${API_BASE_URL}/api/interviews/${encodeURIComponent(cleanApplicationId)}/heartbeat`,
    {
      method: "POST",
    },
    "Could not update interview heartbeat."
  );
}


export async function quitInterview(applicationId) {
  const cleanApplicationId = getCleanApplicationId(applicationId);
  return fetchInterviewJson(
    `${API_BASE_URL}/api/interviews/${encodeURIComponent(cleanApplicationId)}/quit`,
    {
      method: "POST",
    },
    "Could not mark interview as interrupted."
  );
}


export async function evaluateInterviewAnswer(applicationId, questionId, answerText, options = {}) {
  const cleanApplicationId = getCleanApplicationId(applicationId);

  if (!questionId) {
    throw new Error("Question ID missing.");
  }

  if (!String(answerText || "").trim()) {
    throw new Error("Please record an answer before submitting.");
  }

  return fetchInterviewJson(
    `${API_BASE_URL}/api/interview/questions/${encodeURIComponent(cleanApplicationId)}/evaluate`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question_id: questionId,
        answer_text: answerText,
        transcript: options.transcript || "",
        audio_path: options.audioPath || "",
      }),
    },
    "Could not evaluate answer."
  );
}


export async function completeInterview(applicationId) {
  const cleanApplicationId = getCleanApplicationId(applicationId);
  return fetchInterviewJson(
    `${API_BASE_URL}/api/interview/questions/${encodeURIComponent(cleanApplicationId)}/complete`,
    {
      method: "POST",
    },
    "Could not complete interview."
  );
}


export function quitInterviewWithBeacon(applicationId) {
  const cleanApplicationId = String(applicationId || "").trim();

  if (!cleanApplicationId || !navigator.sendBeacon) {
    return false;
  }

  return navigator.sendBeacon(
    `${API_BASE_URL}/api/interviews/${encodeURIComponent(cleanApplicationId)}/quit`
  );
}


export async function saveInterviewAnswer(applicationId, answer) {
  const cleanApplicationId = getCleanApplicationId(applicationId);
  return fetchInterviewJson(
    `${API_BASE_URL}/api/interviews/${encodeURIComponent(cleanApplicationId)}/answers/save`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(answer || {}),
    },
    "Could not save answer."
  );
}


export async function captureLivenessReference(applicationId, payload) {
  const cleanApplicationId = getCleanApplicationId(applicationId);
  return fetchInterviewJson(
    `${API_BASE_URL}/api/interviews/${encodeURIComponent(cleanApplicationId)}/liveness/reference`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload || {}),
    },
    "Could not capture face reference."
  );
}


export async function checkLivenessFrame(applicationId, payload) {
  const cleanApplicationId = getCleanApplicationId(applicationId);
  return fetchInterviewJson(
    `${API_BASE_URL}/api/interviews/${encodeURIComponent(cleanApplicationId)}/liveness/check`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload || {}),
    },
    "Could not run liveness check."
  );
}


export async function validateInterviewToken(token) {
  const cleanToken = String(token || "").trim();

  if (!cleanToken) {
    throw new Error("Interview token missing.");
  }

  return fetchInterviewJson(
    `${API_BASE_URL}/api/interview/validate-token/${encodeURIComponent(cleanToken)}`,
    {
      method: "GET",
    },
    "Could not validate interview link."
  );
}


export async function getQwenHealth() {
  return fetchInterviewJson(
    `${API_BASE_URL}/api/interview/qwen-health`,
    {
      method: "GET",
    },
    "Could not check Qwen health."
  );
}


export async function verifyFaceFrame(applicationId, blob) {
  const cleanApplicationId = getCleanApplicationId(applicationId);

  if (!blob) {
    throw new Error("Live webcam frame is missing.");
  }

  const formData = new FormData();
  formData.append("frame", blob, "live-frame.jpg");

  const url = `${API_BASE_URL}/api/interview/face-verify/${encodeURIComponent(
    cleanApplicationId
  )}`;

  let response;

  try {
    response = await fetch(url, {
      method: "POST",
      body: formData,
    });
  } catch (error) {
    console.error("[Interview] Face verification request failed:", error);
    throw new Error("Could not reach backend for face verification.");
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      getFaceBackendMessage(data) ||
        data?.detail ||
        `Face verification failed. HTTP ${response.status}`
    );
  }

  if (!data) {
    throw new Error("Backend returned an invalid face verification response.");
  }

  return data;
}


function getCleanApplicationId(applicationId) {
  const cleanApplicationId = String(applicationId || "").trim();

  if (!cleanApplicationId) {
    throw new Error("Application ID missing. Please upload resume again.");
  }

  return cleanApplicationId;
}


async function fetchInterviewJson(url, options, fallbackMessage) {
  let response;

  try {
    response = await fetch(url, options);
  } catch (error) {
    console.error("[Interview] API request failed:", error);
    throw new Error("Could not reach backend.");
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      getFaceBackendMessage(data) ||
        data?.detail ||
        `${fallbackMessage} HTTP ${response.status}`
    );
  }

  if (!data) {
    throw new Error("Backend returned an invalid response.");
  }

  return data;
}


function getFaceBackendMessage(data) {
  if (!data) {
    return "";
  }

  const messages = [
    data.message,
    data.error,
    data.data?.error,
  ].filter(Boolean);

  return [...new Set(messages)].join(" ");
}
