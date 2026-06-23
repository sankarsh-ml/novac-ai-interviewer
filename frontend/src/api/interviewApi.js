const API_BASE_URL = "http://127.0.0.1:8000";


export async function verifyFaceFrame(applicationId, blob) {
  const cleanApplicationId = String(applicationId || "").trim();

  if (!cleanApplicationId) {
    throw new Error("Application ID missing. Please upload resume again.");
  }

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