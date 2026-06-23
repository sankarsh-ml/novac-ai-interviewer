const API_BASE_URL = "http://127.0.0.1:8000";


export async function getInterviewQuestions(applicationId) {
  const cleanApplicationId = getCleanApplicationId(applicationId);
  return fetchInterviewJson(
    `${API_BASE_URL}/api/interview/questions/${encodeURIComponent(cleanApplicationId)}`,
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


export async function evaluateInterviewAnswer(applicationId, questionId, answerText) {
  const cleanApplicationId = getCleanApplicationId(applicationId);

  if (!questionId) {
    throw new Error("Question ID missing.");
  }

  if (!String(answerText || "").trim()) {
    throw new Error("Please type an answer before submitting.");
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
      }),
    },
    "Could not evaluate answer."
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


export async function uploadInterviewAudio(
  applicationId,
  audioBlob
) {
  const cleanApplicationId = String(applicationId || "").trim();

  if (!cleanApplicationId) {
    throw new Error("Application ID missing.");
  }

  if (!audioBlob) {
    throw new Error("Audio blob missing.");
  }

  const formData = new FormData();

  formData.append(
    "audio",
    audioBlob,
    "interview.webm"
  );

  const url =
    `${API_BASE_URL}/api/interview/upload-audio/${encodeURIComponent(
      cleanApplicationId
    )}`;

  let response;

  try {
    response = await fetch(url, {
      method: "POST",
      body: formData,
    });
  } catch (error) {
    console.error("[Interview Audio] Upload failed:", error);

    throw new Error(
      "Could not reach backend for audio upload."
    );
  }

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      data?.message ||
      `Audio upload failed. HTTP ${response.status}`
    );
  }

  return data;
}


export async function submitQuestionAudioAnswer(applicationId, questionId, audioBlob) {
  const cleanApplicationId = getCleanApplicationId(applicationId);

  if (!questionId) {
    throw new Error("Question ID missing.");
  }

  if (!audioBlob || audioBlob.size === 0) {
    throw new Error("Audio recording is empty.");
  }

  const formData = new FormData();
  formData.append("audio", audioBlob, `answer-${questionId}.webm`);

  return fetchInterviewJson(
    `${API_BASE_URL}/api/interview/${encodeURIComponent(
      cleanApplicationId
    )}/question/${encodeURIComponent(questionId)}/audio-answer`,
    {
      method: "POST",
      body: formData,
    },
    "Could not submit audio answer."
  );
}


export async function completeInterview(applicationId) {
  const cleanApplicationId = getCleanApplicationId(applicationId);

  return fetchInterviewJson(
    `${API_BASE_URL}/api/interview/${encodeURIComponent(cleanApplicationId)}/complete`,
    {
      method: "POST",
    },
    "Could not complete interview."
  );
}


export async function cleanupInterview(applicationId, options = {}) {
  const cleanApplicationId = getCleanApplicationId(applicationId);

  return fetchInterviewJson(
    `${API_BASE_URL}/api/interview/${encodeURIComponent(cleanApplicationId)}/cleanup`,
    {
      method: "DELETE",
      keepalive: Boolean(options.keepalive),
    },
    "Could not clean up interview."
  );
}
