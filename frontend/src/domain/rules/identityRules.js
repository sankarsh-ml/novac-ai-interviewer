export function canSkipGovernmentId(resumePhotoAvailable) {
  return resumePhotoAvailable === true;
}

export function validateIdentityConfig(config, resumePhotoAvailable) {
  if (config?.requireGovernmentId === false && !canSkipGovernmentId(resumePhotoAvailable)) {
    return "No resume photo was found for this candidate. Indian Government ID verification is required.";
  }

  return "";
}

export function getForcedIdentityConfig(resumePhotoAvailable) {
  if (resumePhotoAvailable) {
    return null;
  }

  return {
    requireGovernmentId: true,
    faceVerificationSource: "government_id",
  };
}

export function getIdentityConfig(data) {
  return data?.identityConfig || data?.identity_config || {};
}

export function isGovernmentIdRequired(data) {
  return getIdentityConfig(data).requireGovernmentId !== false;
}

export function shouldUseResumePhotoVerification(data) {
  const identityConfig = getIdentityConfig(data);
  return (
    identityConfig.requireGovernmentId === false &&
    identityConfig.faceVerificationSource === "resume_photo" &&
    identityConfig.resumePhotoAvailable === true
  );
}

export function isResumePhotoMissingFallback(data) {
  const identityConfig = getIdentityConfig(data);
  return (
    identityConfig.requireGovernmentId === false &&
    identityConfig.faceVerificationSource === "resume_photo" &&
    identityConfig.resumePhotoAvailable !== true
  );
}

export function isGovernmentIdVerified(data) {
  const identity = data?.identityVerification || data?.identity_verification || {};
  const statuses = [
    data?.verificationStatus,
    data?.verification_status,
  ].map((value) => String(value || "").toLowerCase());

  return (
    data?.aadhaarVerified === true ||
    data?.aadhaar_verified === true ||
    data?.governmentIdVerified === true ||
    data?.government_id_verified === true ||
    identity?.isValidIndianGovId === true ||
    identity?.is_valid_indian_gov_id === true ||
    statuses.includes("aadhaar_passed") ||
    statuses.includes("government_id_passed") ||
    statuses.includes("identity_passed") ||
    statuses.includes("verified")
  );
}

export function isFaceVerified(data) {
  return (
    data?.faceVerified === true ||
    data?.face_verified === true ||
    data?.verification_completed === true ||
    String(data?.verificationStatus || "").toLowerCase() === "verified" ||
    String(data?.verification_status || "").toLowerCase() === "verified"
  );
}
