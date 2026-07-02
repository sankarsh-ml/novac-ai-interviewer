import { getApiBaseUrl } from "../config/configLoader.js";
import { getLocalValue, removeLocalValue } from "../storage/localStorageClient.js";

export const ADMIN_TOKEN_KEY = "adminAccessToken";
export const CANDIDATE_TOKEN_KEY = "candidateAccessToken";

export function buildApiUrl(path) {
  if (/^https?:\/\//i.test(String(path))) {
    return path;
  }

  return `${getApiBaseUrl()}${path}`;
}

export function buildAuthenticatedApiUrl(path, auth = "admin") {
  const token = getAuthToken(auth);
  const url = buildApiUrl(path);

  if (!token) {
    return url;
  }

  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}access_token=${encodeURIComponent(token)}`;
}

export async function apiRequest(path, options = {}) {
  const { auth = "admin", body, headers, responseType = "json", ...rest } = options;
  const requestHeaders = { ...(headers || {}) };
  let requestBody = body;
  attachAuthHeader(requestHeaders, auth);

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
    removeTokenOnUnauthorized(response.status, auth);

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

export function apiBeacon(path, body, options = {}) {
  const auth = options.auth || "candidate";
  const headers = {};

  attachAuthHeader(headers, auth);

  if (headers.Authorization) {
    fetch(buildApiUrl(path), {
      method: "POST",
      body,
      headers,
      keepalive: true,
    }).catch(() => {});
    return true;
  }

  if (navigator.sendBeacon) {
    return navigator.sendBeacon(buildApiUrl(path), body);
  }

  return false;
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

function attachAuthHeader(headers, auth) {
  const token = getAuthToken(auth);

  if (token && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`;
  }
}

function getAuthToken(auth) {
  if (auth === "candidate") {
    return getLocalValue(CANDIDATE_TOKEN_KEY, "");
  }

  if (auth === "none") {
    return "";
  }

  return getLocalValue(ADMIN_TOKEN_KEY, "") || getLocalValue("novac_admin_access_token", "");
}

function removeTokenOnUnauthorized(status, auth) {
  if (status !== 401) {
    return;
  }

  if (auth === "candidate") {
    removeLocalValue(CANDIDATE_TOKEN_KEY);
  } else if (auth === "admin") {
    removeLocalValue(ADMIN_TOKEN_KEY);
    removeLocalValue("novac_admin_access_token");
  }
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
