import { useEffect, useRef, useState } from "react";

import { markCandidateVerified } from "@application/useCases/identityUseCases.js";
import { startInterview, verifyFaceFrame } from "@application/useCases/interviewUseCases.js";
import { useDependencies } from "@presentation/hooks/useDependencies.js";
import "@presentation/styles/AadhaarUploadPage.css";
import "@presentation/styles/InterviewPage.css";


function FaceVerificationPage({ applicationSummary, cameraSession, onVerified }) {
  const { identityRepository, interviewRepository } = useDependencies();
  const videoRef = useRef(null);
  const isRequestInFlightRef = useRef(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isStartingInterview, setIsStartingInterview] = useState(false);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [attempts, setAttempts] = useState(0);
  const [matches, setMatches] = useState(0);
  const [lastResult, setLastResult] = useState(null);

  const isCameraRunning = cameraSession?.isCameraRunning;
  const identityConfig = applicationSummary?.identityConfig || applicationSummary?.identity_config || {};
  const usesResumePhoto = (
    identityConfig.requireGovernmentId === false &&
    identityConfig.faceVerificationSource === "resume_photo"
  );
  const resumePhotoMissingFallback = usesResumePhoto && identityConfig.resumePhotoAvailable !== true;

  useEffect(() => {
    if (videoRef.current && cameraSession?.stream) {
      videoRef.current.srcObject = cameraSession.stream;
    }
  }, [cameraSession?.stream, isCameraRunning]);

  if (!applicationSummary) {
    return (
      <main className="aadhaar-page">
        <section className="aadhaar-panel">
          <h1>Face Verification</h1>
          <p className="aadhaar-message">No candidate application is available.</p>
        </section>
      </main>
    );
  }

  const startCamera = async () => {
    setError("");

    try {
      const stream = await cameraSession.startCamera();

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }

      setStatus("ready");
    } catch (cameraError) {
      setStatus("failed");
      setError("Camera permission failed. Please allow camera access.");
    }
  };

  const verifyFace = async () => {
    if (isRequestInFlightRef.current || !videoRef.current) {
      return;
    }

    const video = videoRef.current;

    if (!video.videoWidth || !video.videoHeight || video.readyState < 2) {
      setError("Camera is still warming up. Try again in a moment.");
      return;
    }

    isRequestInFlightRef.current = true;
    setIsVerifying(true);
    setError("");
    setStatus("verifying");

    try {
      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);

      const blob = await new Promise((resolve) => {
        canvas.toBlob(resolve, "image/jpeg", 0.9);
      });

      if (!blob) {
        throw new Error("Could not capture webcam frame.");
      }

      const result = await verifyFaceFrame(interviewRepository, applicationSummary.application_id, blob);
      const nextAttempts = attempts + 1;
      const didMatch = result.match === true || result.verified === true;
      const nextMatches = matches + (didMatch ? 1 : 0);

      setAttempts(nextAttempts);
      setMatches(nextMatches);
      setLastResult(result);

      if (didMatch || nextMatches >= 1) {
        await markCandidateVerified(
          identityRepository,
          applicationSummary.application_id,
          result.reference_source || "",
          typeof result.score === "number" ? result.score : null,
          nextAttempts,
          Math.max(1, nextMatches)
        );
        setStatus("passed");
        return;
      }

      setStatus("failed");
      setError("Face verification failed. Please ensure your face is clearly visible and try again.");
    } catch (apiError) {
      setStatus("failed");
      setError(apiError.message || "Face verification failed.");
    } finally {
      isRequestInFlightRef.current = false;
      setIsVerifying(false);
    }
  };

  const isVerified = status === "passed";

  const handleStartInterview = async () => {
    setError("");
    setIsStartingInterview(true);

    try {
      await startInterview(interviewRepository, applicationSummary.application_id);
      onVerified({ ...applicationSummary, faceVerified: true });
    } catch (apiError) {
      console.error("[FaceVerification] start interview failed; continuing to interview route:", apiError);
      onVerified({ ...applicationSummary, faceVerified: true });
    } finally {
      setIsStartingInterview(false);
    }
  };

  return (
    <main className="aadhaar-page">
      <section className="aadhaar-panel">
        <header className="aadhaar-header">
          <p className="eyebrow">Identity Check</p>
          <h1>Face Verification</h1>
          <p>
            {usesResumePhoto
              ? "Face verification will be completed using the photo from your resume."
              : "Use the camera to verify your live face against the verified identity document."}
          </p>
        </header>

        {resumePhotoMissingFallback && (
          <p className="aadhaar-message">Resume photo is not available. Please complete Indian Government ID verification.</p>
        )}

        <div className="video-frame large">
          <video className="video-preview" ref={videoRef} autoPlay playsInline muted />
          {!isCameraRunning && <p className="video-placeholder">Camera preview will appear here.</p>}
        </div>

        <div className="camera-actions centered">
          <button className="camera-button start" type="button" onClick={startCamera} disabled={isCameraRunning || isVerified}>
            Start Camera
          </button>
          <button
            className="camera-button start"
            type="button"
            onClick={verifyFace}
            disabled={!isCameraRunning || isVerifying || isVerified}
          >
            {isVerifying ? "Verifying..." : "Verify Face"}
          </button>
        </div>

        <section className={`face-status ${status}`}>
          <p className="face-status-text">{getStatusMessage(status)}</p>
          <div className="face-details compact">
            <span>Attempts: {attempts}/5</span>
            <span>Matches: {matches}/1</span>
          </div>
          {lastResult?.message && status === "failed" && <p className="face-error">{lastResult.message}</p>}
          {error && <p className="face-error">{error}</p>}
        </section>

        {isVerified && (
          <button
            className="aadhaar-upload-button continue-button"
            type="button"
            onClick={handleStartInterview}
            disabled={isStartingInterview}
          >
            {isStartingInterview ? "Starting Interview..." : "Start Interview"}
          </button>
        )}
      </section>
    </main>
  );
}


function getStatusMessage(status) {
  if (status === "passed") {
    return "Verified";
  }

  if (status === "verifying") {
    return "Verifying...";
  }

  if (status === "failed") {
    return "Face verification failed. Please try again.";
  }

  if (status === "ready") {
    return "Camera ready. Verify your face when you are centered.";
  }

  return "Start camera to begin face verification.";
}


export default FaceVerificationPage;
