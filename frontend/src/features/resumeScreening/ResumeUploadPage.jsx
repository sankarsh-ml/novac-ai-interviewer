import { useEffect, useRef, useState } from "react";
import { uploadBulkResumes } from "../../services/resumeApi.js";
import { PROCESSING_LEAVE_MESSAGE } from "../../config/appConfig.js";
import "../../styles/UploadResumePage.css";


function UploadResumesPage({job,onBack}) 
{
  const isMountedRef = useRef(true);
  const isUploadingRef = useRef(false);

  const [files,setFiles] =useState([]);

  const [isUploading, setIsUploading] = useState(false);

  const [uploadResult, setUploadResult] =useState(null);

  useEffect(() => {
  console.log("isUploading =", isUploading);
}, [isUploading]);

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
    if (!files.length) return;

    setIsUploading(true);
    isUploadingRef.current = true;
    setUploadResult(null);

    try {
      const data = await uploadBulkResumes(job.id, files);
      setUploadResult(data);

      // FIRST stop uploading
      setIsUploading(false);
      isUploadingRef.current = false;

      // THEN clear files
      setFiles([]);

      // THEN wait one frame so React updates
      requestAnimationFrame(() => {
        alert(
          `✅ Processing completed successfully!\n\n${data.count} resume(s) processed.`
        );
      });

    } catch (err) {
      console.error(err);

      setIsUploading(false);
      isUploadingRef.current = false;

      alert("❌ Failed to process resumes.");
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
            disabled={!files.length || isUploading}>

            {isUploading ? "Processing..." : "Process Resumes"}
          </button>

        {uploadResult && (
        <div className="upload-summary">

          <div className="summary-header">
            <span className="summary-icon">✅</span>

            <div>
              <h3>Upload Complete</h3>
              <p>
                {uploadResult.count || 0} resume(s) processed successfully
              </p>
            </div>
          </div>

          <div className="summary-list">
            {(uploadResult.applications || []).map((item) => (
              <div className="summary-item" key={item.application_id}>
                <div className="summary-name">
                  📄 {item.candidate_name || item.file_name}
                </div>

                <div
                  className={
                    item.ats_status === "passed"
                      ? "status-pass"
                      : "status-fail"
                  }
                >
                  {item.ats_status === "passed" ? "Passed" : "Failed"}
                </div>
              </div>
            ))}

            {(uploadResult.failed || []).map((item) => (
              <div className="summary-item" key={item.file_name}>
                <div className="summary-name">
                  📄 {item.file_name}
                </div>

                <div className="status-error">
                  {item.error}
                </div>
              </div>
            ))}
          </div>

        </div>
      )}

      </div>

    </div>

  </main>
);
}

export default UploadResumesPage;

