import { useState } from "react";
import "../styles/UploadResumePage.css";
function UploadResumesPage({job,onBack}) 
{

  const [files,setFiles] =
    useState([]);
  const [isUploading, setIsUploading] =
    useState(false);
  const [uploadResult, setUploadResult] =
    useState(null);

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
        "http://127.0.0.1:8000/api/resume/bulk-upload",
        {
            method: "POST",
            body: formData
        }
        );

        const data = await response.json();

        setUploadResult(data);
        setFiles([]);
    } catch (error) {
        console.error(error);
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
    setIsUploading(false);
    }
  };

  return (
  <main className="upload-page">

    <div className="upload-container">

      <button
        className="upload-back-button"
        onClick={onBack}
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

