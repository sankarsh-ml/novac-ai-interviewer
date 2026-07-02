import { useState } from "react";

import { uploadIndianGovernmentId } from "@application/useCases/identityUseCases.js";
import GovernmentIdUpload from "@presentation/components/identity/GovernmentIdUpload.jsx";
import { useDependencies } from "@presentation/hooks/useDependencies.js";
import "@presentation/styles/AadhaarUploadPage.css";


const ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".pdf"];


function AadhaarUploadPage({ applicationSummary, onVerified }) {
  const { identityRepository } = useDependencies();
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [verification, setVerification] = useState(null);
  const identityConfig = applicationSummary?.identityConfig || applicationSummary?.identity_config || {};
  const resumePhotoMissingFallback =
    identityConfig.requireGovernmentId === false &&
    identityConfig.faceVerificationSource === "resume_photo" &&
    identityConfig.resumePhotoAvailable !== true;

  if (!applicationSummary) {
    return (
      <main className="aadhaar-page">
        <section className="aadhaar-panel">
          <h1>Indian Government ID Verification</h1>
          <p className="aadhaar-message">No resume application is available.</p>
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
      setError("Please choose a JPG, PNG, or PDF Indian Government ID file.");
      return;
    }

    setFile(selectedFile);
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please select an Indian Government ID image or PDF.");
      return;
    }

    setLoading(true);
    setError("");
    setVerification(null);

    try {
      const response = await uploadIndianGovernmentId(identityRepository, applicationSummary.application_id, file);
      setVerification(response.data);
    } catch (apiError) {
      setError(apiError.message || "Government ID verification failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="aadhaar-page">
      <section className="aadhaar-panel">
        <header className="aadhaar-header">
          <p className="eyebrow">Identity Check</p>
          <h1>Indian Government ID Verification</h1>
          <p>Please upload a clear official Indian government ID image or PDF for identity verification.</p>
        </header>

        {resumePhotoMissingFallback && (
          <p className="aadhaar-message">Resume photo is not available. Please complete Indian Government ID verification.</p>
        )}

        <GovernmentIdUpload>
          <label className="aadhaar-file-label" htmlFor="aadhaar-file">
            <span>{file ? file.name : "Select Indian Government ID image or PDF"}</span>
            <input
              id="aadhaar-file"
              type="file"
              accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf"
              onChange={handleFileChange}
            />
          </label>

          <button className="aadhaar-upload-button" type="button" onClick={handleUpload} disabled={!file || loading}>
            {loading ? "Verifying Government ID..." : "Upload Indian Government ID"}
          </button>
        </GovernmentIdUpload>

        {error && <p className="error-message">{error}</p>}

        {verification && (
          <section className="aadhaar-result">
            <h2>Government ID verification status: {formatStatus(verification.government_id_verification_status || verification.aadhaar_verification_status)}</h2>
            <div className="aadhaar-result-grid">
              <ResultItem label="Resume name" value={verification.resume_name} />
              <ResultItem label="Document type" value={formatStatus(verification.documentType || verification.document_type)} />
              <ResultItem label="Government ID name" value={verification.government_id_name || verification.aadhaar_name} />
              <ResultItem label="Name match score" value={verification.name_match_score} />
              <ResultItem label="Photo stored" value={verification.aadhaar_photo_stored ? "Yes" : "No"} />
              <ResultItem label="Photo match" value={formatStatus(verification.photo_match_status)} />
              <ResultItem label="Document ID / ID Number" value={verification.id_number || verification.masked_aadhaar_number || verification.extractedFields?.idNumber || "Not available"} />
            </div>
            <button
              className="aadhaar-upload-button continue-button"
              type="button"
              onClick={() => onVerified({ ...verification, aadhaarVerified: true, governmentIdVerified: true })}
            >
              Continue to Face Verification
            </button>
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


function formatStatus(value) {
  return String(value || "Not Available")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
