import { useState } from "react";

import { uploadAadhaar } from "../api/kycApi.js";
import "../styles/AadhaarUploadPage.css";


const ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".pdf"];


function AadhaarUploadPage({ applicationSummary, onBackHome, onVerified }) {
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [verification, setVerification] = useState(null);

  if (!applicationSummary) {
    return (
      <main className="aadhaar-page">
        <section className="aadhaar-panel">
          <h1>Aadhaar Verification</h1>
          <p className="aadhaar-message">No resume application is available.</p>
          <button className="aadhaar-home-button" type="button" onClick={onBackHome}>
            Back Home
          </button>
        </section>
      </main>
    );
  }

  const handleFileChange = (event) => {
    const selectedFile = event.target.files?.[0] || null;
    setError("");
    setVerification(null);

    if (!selectedFile) {
      setFile(null);
      return;
    }

    const fileName = selectedFile.name.toLowerCase();
    if (!ALLOWED_EXTENSIONS.some((extension) => fileName.endsWith(extension))) {
      setFile(null);
      setError("Please choose a JPG, PNG, or PDF Aadhaar file.");
      return;
    }

    setFile(selectedFile);
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please select an Aadhaar image or PDF.");
      return;
    }

    setLoading(true);
    setError("");
    setVerification(null);

    try {
      const response = await uploadAadhaar(applicationSummary.application_id, file);
      setVerification(response.data);
      window.setTimeout(() => onVerified(response.data), 900);
    } catch (apiError) {
      setError(apiError.message || "Aadhaar verification failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="aadhaar-page">
      <section className="aadhaar-panel">
        <button className="back-button" type="button" onClick={onBackHome}>
          Back Home
        </button>

        <header className="aadhaar-header">
          <p className="eyebrow">Identity Check</p>
          <h1>Aadhaar Verification</h1>
          <p>Please upload a clear Aadhaar card image or PDF for identity verification.</p>
        </header>

        <section className="aadhaar-upload-box">
          <label className="aadhaar-file-label" htmlFor="aadhaar-file">
            <span>{file ? file.name : "Select Aadhaar image or PDF"}</span>
            <input
              id="aadhaar-file"
              type="file"
              accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf"
              onChange={handleFileChange}
            />
          </label>

          <button className="aadhaar-upload-button" type="button" onClick={handleUpload} disabled={!file || loading}>
            {loading ? "Verifying Aadhaar..." : "Upload Aadhaar"}
          </button>
        </section>

        {error && <p className="error-message">{error}</p>}

        {verification && (
          <section className="aadhaar-result">
            <h2>Aadhaar verification status: {verification.aadhaar_verification_status}</h2>
            <div className="aadhaar-result-grid">
              <ResultItem label="Resume name" value={verification.resume_name} />
              <ResultItem label="Aadhaar name" value={verification.aadhaar_name} />
              <ResultItem label="Name match score" value={verification.name_match_score} />
              <ResultItem label="Photo stored" value={verification.aadhaar_photo_stored ? "Yes" : "No"} />
              <ResultItem label="Photo match" value={verification.photo_match_status} />
              <ResultItem label="Masked Aadhaar" value={verification.masked_aadhaar_number || "Not available"} />
            </div>
          </section>
        )}
      </section>
    </main>
  );
}


function ResultItem({ label, value }) {
  return (
    <article className="aadhaar-result-item">
      <span>{label}</span>
      <strong>{value ?? "Not available"}</strong>
    </article>
  );
}


export default AadhaarUploadPage;
