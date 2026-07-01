import { API_BASE_URL } from "../../config/apiConfig.js";

export function buildApiUrl(path) {
  if (/^https?:\/\//i.test(String(path))) {
    return path;
  }

  return `${API_BASE_URL}${path}`;
}

export async function apiRequest(path, options = {}) {
  const { body, headers, responseType = "json", ...rest } = options;
  const requestHeaders = { ...(headers || {}) };
  let requestBody = body;

  if (body && !(body instanceof FormData) && typeof body !== "string") {
    requestHeaders["Content-Type"] = requestHeaders["Content-Type"] || "application/json";
    requestBody = JSON.stringify(body);
  }

  let response;

  try {
    response = await fetch(buildApiUrl(path), {
      ...rest,
      headers: requestHeaders,
      body: requestBody,
    });
  } catch (error) {
    console.error("[API] request failed:", error);
    throw new Error("Could not reach backend.");
  }

  if (responseType === "blob") {
    return parseBlobResponse(response);
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw buildApiError(getBackendMessage(data) || `Request failed. HTTP ${response.status}`, response.status, data);
  }

  if (!data) {
    throw new Error("Backend returned an invalid response.");
  }

  if (data.success === false) {
    throw buildApiError(data.message || data.detail || "Request failed.", response.status, data);
  }

  return data;
}

export function apiBeacon(path, body) {
  if (!navigator.sendBeacon) {
    return false;
  }

  return navigator.sendBeacon(buildApiUrl(path), body);
}

async function parseBlobResponse(response) {
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw buildApiError(getBackendMessage(data) || `Request failed. HTTP ${response.status}`, response.status, data);
  }

  const blob = await response.blob();
  const filename = getFilenameFromDisposition(response.headers.get("Content-Disposition"));

  if (!blob || blob.size === 0) {
    throw new Error("Backend returned an empty file.");
  }

  return { blob, filename };
}

function getBackendMessage(data) {
  if (!data) {
    return "";
  }

  return [data.message, data.detail, data.error, data.data?.error].filter(Boolean).join(" ");
}

function buildApiError(message, status, data) {
  const error = new Error(message);
  error.status = status;
  error.data = data;
  return error;
}

function getFilenameFromDisposition(disposition) {
  const match = String(disposition || "").match(/filename="?([^"]+)"?/i);
  return match ? match[1] : "";
}
