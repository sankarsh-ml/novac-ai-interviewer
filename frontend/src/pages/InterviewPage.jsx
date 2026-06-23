import { useEffect, useRef, useState } from "react";

import {verifyFaceFrame,uploadInterviewAudio} from "../api/interviewApi.js";
import "../styles/InterviewPage.css";


function InterviewPage({ applicationSummary, onBackHome }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const faceIntervalRef = useRef(null);
  const faceAttemptCountRef = useRef(0);
  const faceMatchCountRef = useRef(0);
  const faceVerificationDoneRef = useRef(false);
  const isFaceRequestInFlightRef = useRef(false);
  const [cameraError, setCameraError] = useState("");
  const [isCameraOn, setIsCameraOn] = useState(false);
  const [faceStatus, setFaceStatus] = useState("idle");
  const [faceScore, setFaceScore] = useState(null);
  const [faceMatchCount, setFaceMatchCount] = useState(0);
  const [faceAttemptCount, setFaceAttemptCount] = useState(0);
  const [isFaceVerified, setIsFaceVerified] = useState(false);
  const [faceReferenceSource, setFaceReferenceSource] = useState("");
  const [faceError, setFaceError] = useState("");

  const [isInterviewRunning, setIsInterviewRunning] = useState(false);
  const [interviewCompleted, setInterviewCompleted] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, []);

  useEffect(() => {
    if (!isCameraOn) {
      clearFaceVerificationInterval();
      return;
    }

    setFaceStatus("verifying");
    clearFaceVerificationInterval();

    faceIntervalRef.current = window.setInterval(() => {
      captureAndVerifyFaceFrame();
    }, 2000);

    return () => {
      clearFaceVerificationInterval();
    };
  }, [isCameraOn, applicationSummary?.application_id]);

  const startCamera = async () => {
    setCameraError("");
    resetFaceVerification();

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setIsCameraOn(true);
    } catch (error) {
      console.error("Camera permission failed:", error);
      setCameraError("Camera permission failed. Please allow camera and microphone access.");
    }
  };

  const stopCamera = () => {
    clearFaceVerificationInterval();

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsCameraOn(false);
  };

  const clearFaceVerificationInterval = () => {
    if (faceIntervalRef.current) {
      window.clearInterval(faceIntervalRef.current);
      faceIntervalRef.current = null;
    }
  };

  const resetFaceVerification = () => {
    clearFaceVerificationInterval();
    faceAttemptCountRef.current = 0;
    faceMatchCountRef.current = 0;
    faceVerificationDoneRef.current = false;
    isFaceRequestInFlightRef.current = false;
    setFaceStatus("idle");
    setFaceScore(null);
    setFaceMatchCount(0);
    setFaceAttemptCount(0);
    setIsFaceVerified(false);
    setFaceReferenceSource("");
    setFaceError("");
  };

  const startAudioRecording = () => {
    console.log("startAudioRecording called");
    console.log("streamRef.current =", streamRef.current);
    if (!streamRef.current) return;

    try {
      audioChunksRef.current = [];

      const recorder = new MediaRecorder(streamRef.current);
      console.log("Recorder state:",recorder.state);
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
          console.log("Chunk received:",event.data.size);
        }
      };

      recorder.start(1000);

      mediaRecorderRef.current = recorder;

      console.log("Audio recording started");
    } catch (error) {
      console.error("Audio recording failed:", error);
    }
  };

  const stopAudioRecording = () => {
    return new Promise((resolve) => {

      const recorder = mediaRecorderRef.current;

      console.log("Recorder at stop =", recorder);

      if (!recorder) {
        console.log("Recorder is NULL");
        resolve(null);
        return;
      }

      recorder.onstop = () => {
        console.log("Chunks =", audioChunksRef.current.length);

        const audioBlob = new Blob(
          audioChunksRef.current,
          { type: "audio/webm" }
        );

        console.log("Blob size =", audioBlob.size);

        resolve(audioBlob);
      };

      recorder.stop();
    });
  };

  const startInterview = () => {
    console.log("START INTERVIEW CLICKED");
    console.log("streamRef.current =", streamRef.current);

    startAudioRecording();

    console.log("mediaRecorderRef.current =", mediaRecorderRef.current);

    setIsInterviewRunning(true);
    setInterviewCompleted(false);

    console.log("Interview started");
  };

  const endInterview = async () => {
    const audioBlob = await stopAudioRecording();

    console.log("Interview ended");
    console.log(audioBlob);

    try {
      const result = await uploadInterviewAudio(
        applicationSummary.application_id,
        audioBlob
      );

      console.log("Upload success:", result);
    } catch (error) {
      console.error("Upload failed:", error);
    }

    setIsInterviewRunning(false);
    setInterviewCompleted(true);
  };
  const captureAndVerifyFaceFrame = async () => {
    if (
      faceVerificationDoneRef.current ||
      isFaceRequestInFlightRef.current ||
      !videoRef.current
    ) {
      return;
    }

    const video = videoRef.current;

    if (!video.videoWidth || !video.videoHeight || video.readyState < 2) {
      return;
    }

    isFaceRequestInFlightRef.current = true;

    try {
      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;

      const context = canvas.getContext("2d");
      context.drawImage(video, 0, 0, canvas.width, canvas.height);

      const blob = await new Promise((resolve) => {
        canvas.toBlob(resolve, "image/jpeg", 0.9);
      });

      if (!blob) {
        throw new Error("Could not capture webcam frame.");
      }

      const result = await verifyFaceFrame(applicationSummary?.application_id, blob);
      const nextAttemptCount = faceAttemptCountRef.current + 1;
      const nextMatchCount = faceMatchCountRef.current + (result.match ? 1 : 0);

      faceAttemptCountRef.current = nextAttemptCount;
      faceMatchCountRef.current = nextMatchCount;

      setFaceAttemptCount(nextAttemptCount);
      setFaceMatchCount(nextMatchCount);
      setFaceScore(typeof result.score === "number" ? result.score : null);
      setFaceReferenceSource(result.reference_source || "");
      setFaceError(result.success === false ? getFaceBackendMessage(result) : "");

      if (nextMatchCount >= 3) {
        faceVerificationDoneRef.current = true;
        setIsFaceVerified(true);
        setFaceStatus("passed");
        clearFaceVerificationInterval();
        return;
      }

      if (nextAttemptCount >= 5) {
        faceVerificationDoneRef.current = true;
        setIsFaceVerified(false);
        setFaceStatus("failed");
        clearFaceVerificationInterval();
        return;
      }

      setFaceStatus("verifying");
    } catch (error) {
      console.error("Face verification failed:", error);
      faceVerificationDoneRef.current = true;
      setIsFaceVerified(false);
      setFaceStatus("failed");
      setFaceError(error.message || "Face verification failed.");
      clearFaceVerificationInterval();
    } finally {
      isFaceRequestInFlightRef.current = false;
    }
  };

  const handleBackHome = () => {
    stopCamera();
    onBackHome();
  };

  const faceStatusText = (() => {
    if (faceStatus === "passed") {
      return "Face verified successfully";
    }

    if (faceStatus === "failed") {
      return "Face verification failed. Please ensure your face is clearly visible.";
    }

    if (isCameraOn) {
      return "Verifying face...";
    }

    return "Start camera to verify face.";
  })();

  return (
    <main className="interview-page">
      <section className="interview-panel">
        <button className="back-button" type="button" onClick={handleBackHome}>
          Back Home
        </button>

        <header className="interview-header">
          <p className="eyebrow">Interview</p>
          <h1>Interview Session</h1>
          <p>Please keep your face visible and stay ready for the interview.</p>
        </header>

        <div className="video-frame">
          <video className="video-preview" ref={videoRef} autoPlay playsInline muted />
          {!isCameraOn && <p className="video-placeholder">Camera preview will appear here.</p>}
        </div>

        <div className="camera-actions">
          <button className="camera-button start" type="button" onClick={startCamera} disabled={isCameraOn}>
            Start Camera
          </button>
          <button className="camera-button stop" type="button" onClick={stopCamera} disabled={!isCameraOn}>
            Stop Camera
          </button>
        </div>

        {cameraError && <p className="error-message">{cameraError}</p>}

        <section className={`face-status ${faceStatus}`}>
          <p className="face-status-text">{faceStatusText}</p>
          <div className="face-details">
            <span>
              Attempts: {faceAttemptCount}/5
            </span>
            <span>
              Matches: {faceMatchCount}/3
            </span>
            <span>
              Score: {faceScore === null ? "--" : faceScore.toFixed(4)}
            </span>
            <span>
              Reference: {faceReferenceSource ? toTitleCase(faceReferenceSource) : "--"}
            </span>
          </div>
          {faceError && <p className="face-error">{faceError}</p>}
        </section>
        
        <section className="interview-placeholder">
            {!isFaceVerified && (
              <p>
                Face verification is required before the interview can begin.
              </p>
            )}

            {isFaceVerified && !isInterviewRunning && !interviewCompleted && (
              <>
                <p>Face verified successfully.</p>

                <button
                  className="camera-button start"
                  type="button"
                  onClick={startInterview}
                >
                  Start Interview
                </button>
              </>
            )}

            {isInterviewRunning && (
              <>
                <p>Interview in progress...</p>

                <button
                  className="camera-button stop"
                  type="button"
                  onClick={endInterview}
                >
                  End Interview
                </button>
              </>
            )}

            {interviewCompleted && (
              <p>
                Interview completed successfully.
              </p>
            )}

        </section>
      </section>
    </main>
  );
}


function toTitleCase(value) {
  return String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}


function getFaceBackendMessage(data) {
  if (!data) {
    return "";
  }

  const messages = [
    data.message,
    data.error,
    data.data?.error,
  ].filter(Boolean);

  return [...new Set(messages)].join(" ");
}


export default InterviewPage;
