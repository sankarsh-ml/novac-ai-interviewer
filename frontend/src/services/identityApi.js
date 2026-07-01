import { apiRequest } from "../infrastructure/api/apiClient.js";
import { endpoints } from "../infrastructure/api/endpoints.js";

function cleanApplicationId(applicationId) {
  const value = String(applicationId || "").trim();
  if (!value) {
    throw new Error("Candidate ID missing.");
  }
  return value;
}

export function uploadGovernmentId(applicationId, identityFile) {
  if (!identityFile) {
    throw new Error("Please select an Indian Government ID file.");
  }

  const formData = new FormData();
  formData.append("aadhaar_file", identityFile);

  return apiRequest(endpoints.identityUpload(cleanApplicationId(applicationId)), {
    method: "POST",
    body: formData,
  });
}

export const uploadIndianGovernmentId = uploadGovernmentId;
export const uploadAadhaar = uploadGovernmentId;

export function getCandidateVerificationData(applicationId) {
  return apiRequest(endpoints.candidateVerification(cleanApplicationId(applicationId)), { method: "GET" });
}

export function getVerificationStatus(applicationId) {
  return apiRequest(endpoints.verificationStatus(cleanApplicationId(applicationId)), { method: "GET" });
}

export function getIdentityConfig(applicationId) {
  return getVerificationStatus(applicationId);
}

export function markCandidateVerified(applicationId, referenceSource, faceScore, attempts = 1, matches = 1) {
  return apiRequest(endpoints.markVerified(cleanApplicationId(applicationId)), {
    method: "POST",
    body: {
      reference_source: referenceSource || "",
      face_score: typeof faceScore === "number" ? faceScore : null,
      attempts,
      matches,
    },
  });
}
