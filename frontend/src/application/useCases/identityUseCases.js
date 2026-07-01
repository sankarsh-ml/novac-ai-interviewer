import {
  isFaceVerified,
  isGovernmentIdRequired,
  isResumePhotoMissingFallback,
  shouldUseResumePhotoVerification,
} from "@domain/rules/identityRules.js";

export function uploadGovernmentId(identityRepository, applicationId, identityFile) {
  return identityRepository.uploadGovernmentId(applicationId, identityFile);
}

export const uploadIndianGovernmentId = uploadGovernmentId;
export const uploadAadhaar = uploadGovernmentId;

export function fetchCandidateVerificationData(identityRepository, applicationId) {
  return identityRepository.getCandidateVerificationData(applicationId);
}

export function fetchVerificationStatus(identityRepository, applicationId) {
  return identityRepository.getVerificationStatus(applicationId);
}

export function markCandidateVerified(identityRepository, applicationId, referenceSource, faceScore, attempts, matches) {
  return identityRepository.markCandidateVerified(applicationId, referenceSource, faceScore, attempts, matches);
}

export function getCandidateRouteTarget(routeType, verificationData) {
  if (routeType === "verify" && shouldUseResumePhotoVerification(verificationData)) {
    return "face-verification";
  }

  if (isResumePhotoMissingFallback(verificationData)) {
    return "aadhaar";
  }

  if (isGovernmentIdRequired(verificationData) && !isGovernmentIdVerified(verificationData)) {
    return "aadhaar";
  }

  if (isFaceVerified(verificationData)) {
    return "interview";
  }

  return "face-verification";
}

export function isGovernmentIdVerified(data) {
  const identity = data?.identityVerification || data?.identity_verification || {};
  return (
    data?.aadhaarVerified === true ||
    data?.aadhaar_verified === true ||
    data?.governmentIdVerified === true ||
    data?.government_id_verified === true ||
    identity?.isValidIndianGovId === true ||
    identity?.is_valid_indian_gov_id === true ||
    ["aadhaar_passed", "government_id_passed", "identity_passed", "verified"].includes(
      String(data?.verification_status || data?.verificationStatus || "").toLowerCase()
    )
  );
}
