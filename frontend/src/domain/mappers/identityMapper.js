export function getIdentityMode(identityConfig, resumePhotoAvailable) {
  return resumePhotoAvailable && identityConfig?.requireGovernmentId === false
    ? "resume_photo"
    : "government_id";
}
