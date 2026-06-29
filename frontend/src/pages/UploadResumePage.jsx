import { useEffect, useRef, useState } from "react";
import "../styles/UploadResumePage.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const PROCESSING_LEAVE_MESSAGE = "Processing is still running. Are you sure you want to leave this page?";

function UploadResumesPage({job,onBack}) 
{
  const isMountedRef = useRef(true);
  const isUploadingRef = useRef(false);

  const [files,setFiles] =
    useState([]);
  const [isUploading, setIsUploading] =
    useState(false);
  const [uploadResult, setUploadResult] =
    useState(null);

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
      isUploadingRef.current = false;
    };
  }, []);

  useEffect(() => {
    isUploadingRef.current = isUploading;
  }, [isUploading]);

  useEffect(() => {
    if (!isUploading) {
      return;
    }

    const handleBeforeUnload = (event) => {
      event.preventDefault();
      event.returnValue = PROCESSING_LEAVE_MESSAGE;
      return PROCESSING_LEAVE_MESSAGE;
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [isUploading]);

  useEffect(() => {
    window.history.pushState({ uploadResumesPage: true }, "", window.location.href);

    const handlePopState = () => {
      if (!isUploadingRef.current) {
        onBack();
        return;
      }

      if (window.confirm(PROCESSING_LEAVE_MESSAGE)) {
        isUploadingRef.current = false;
        onBack();
        return;
      }

      window.history.pushState({ uploadResumesPage: true }, "", window.location.href);
    };

    window.addEventListener("popstate", handlePopState);

    return () => {
      window.removeEventListener("popstate", handlePopState);
    };
  }, [onBack]);

  const handleBack = () => {
    if (isUploadingRef.current && !window.confirm(PROCESSING_LEAVE_MESSAGE)) {
      return;
    }

    isUploadingRef.current = false;
    onBack();
  };

  const uploadResumes = async () => {

    try {
    const formData =
        new FormData();

        formData.append(
        "job_id",
        job.id
        );

        files.forEach(file => {
        formData.append(
            "resumes",
            file
        );
        });

        setIsUploading(true);
        setUploadResult(null);

        const response = await fetch(
        `${API_BASE_URL}/api/resume/bulk-upload`,
        {
            method: "POST",
            body: formData
        }
        );

        const data = await response.json();

        if (!isMountedRef.current) {
          return;
        }

        setUploadResult(data);
        setFiles([]);
    } catch (error) {
        console.error(error);
        if (!isMountedRef.current) {
          return;
        }
        setUploadResult({
          count: 0,
          failed: [
            {
              file_name: "Upload",
              error: "Failed to upload resumes"
            }
          ]
        });
    } finally {
      if (isMountedRef.current) {
        setIsUploading(false);
      }
      isUploadingRef.current = false;
    }
  };

  return (
  <main className="upload-page">

    <div className="upload-container">

      <button
        className="upload-back-button"
        onClick={handleBack}
      >
        Back
      </button>

      <div className="upload-card">

        <h1 className="upload-title">
          Upload Resumes
        </h1>

        <p className="upload-subtitle">
          Upload multiple PDF resumes for ATS screening.
        </p>

        <div className="file-upload-box">

          <label
            htmlFor="resume-upload"
            className="upload-label"
            >
            <div className="upload-icon">
                📄
            </div>

            <div className="upload-main-text">
                Click to Upload Resumes
            </div>

            <div className="upload-secondary-text">
                PDF files only • Multiple files supported
            </div>
            </label>

            <input
            id="resume-upload"
            type="file"
            multiple
            accept=".pdf"
            style={{ display: "none" }}
            onChange={(e) =>
                setFiles([...e.target.files])
            }
            />

          <div className="resume-count">
                {files.length} Resume(s) Selected
                </div>

                {files.length > 0 && (
                <div className="selected-files">
                    {files.map((file, index) => (
                    <div key={index}>
                        📄 {file.name}
                    </div>
                    ))}
                </div>
                )}

        </div>

        <button
          className="process-button"
          onClick={uploadResumes}
          disabled={!files.length || isUploading}
        >
          {isUploading ? "Processing..." : "Process Resumes"}
        </button>

        {uploadResult && (
          <div className="selected-files">
            <strong>
              Processed {uploadResult.count || 0} resume(s)
            </strong>
            {(uploadResult.applications || []).map((item) => (
              <div key={item.application_id}>
                {item.candidate_name || item.file_name} - {item.ats_status || item.processing_status}
                {item.duplicate ? " (duplicate)" : ""}
                {item.error ? ` - ${item.error}` : ""}
              </div>
            ))}
            {(uploadResult.failed || []).map((item) => (
              <div key={item.file_name}>
                {item.file_name} - {item.error}
              </div>
            ))}
          </div>
        )}

      </div>

    </div>

  </main>
);
}

export default UploadResumesPage;

