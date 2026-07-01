import { uploadBulkResumes, uploadResume } from "../../services/resumeApi.js";

export function useResumeUpload() {
  return {
    uploadResume,
    uploadBulkResumes,
  };
}
