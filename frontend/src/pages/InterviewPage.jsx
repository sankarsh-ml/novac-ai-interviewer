import { useEffect, useRef, useState } from "react";

import {
  cleanupInterview,
  completeInterview,
  getInterviewQuestions,
  submitQuestionAudioAnswer,
  verifyFaceFrame,
} from "../api/interviewApi.js";
import "../styles/InterviewPage.css";


const AUTO_ADVANCE_DELAY_MS = 1000;


function InterviewPage({ applicationSummary, onBackHome }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const recorderStreamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const lastAudioUrlRef = useRef(null);
  const faceAttemptCountRef = useRef(0);
  const faceMatchCountRef = useRef(0);
  const faceVerificationDoneRef = useRef(false);
  const isFaceRequestInFlightRef = useRef(false);
  const autoAdvanceTimerRef = useRef(null);
  const isMountedRef = useRef(true);
  const hasInterviewStartedRef = useRef(false);
  const phaseRef = useRef("ready");

  const [cameraError, setCameraError] = useState("");
  const [isCameraRunning, setIsCameraRunning] = useState(false);
  const [faceStatus, setFaceStatus] = useState("idle");
  const [faceScore, setFaceScore] = useState(null);
  const [faceMatchCount, setFaceMatchCount] = useState(0);
  const [faceAttemptCount, setFaceAttemptCount] = useState(0);
  const [isFaceVerified, setIsFaceVerified] = useState(false);
  const [faceReferenceSource, setFaceReferenceSource] = useState("");
  const [faceError, setFaceError] = useState("");
  const [isVerifyingFace, setIsVerifyingFace] = useState(false);
  const [phase, setPhase] = useState("ready");
  const [answerState, setAnswerState] = useState("idle");
  const [questions, setQuestions] = useState([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [statusMessage, setStatusMessage] = useState("");
  const [questionGenerationError, setQuestionGenerationError] = useState("");
  const [answerError, setAnswerError] = useState("");
  const [lastAudioDebug, setLastAudioDebug] = useState(null);
  const [hasInterviewStarted, setHasInterviewStarted] = useState(false);

  useEffect(() => {
    hasInterviewStartedRef.current = hasInterviewStarted;
  }, [hasInterviewStarted]);

  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);

  useEffect(() => {
    return () => {
      cleanupUnfinishedInterview();
      isMountedRef.current = false;
      clearAutoAdvanceTimer();
      stopRecorderTracks();

      if (lastAudioUrlRef.current) {
        URL.revokeObjectURL(lastAudioUrlRef.current);
        lastAudioUrlRef.current = null;
      }

      stopCamera();
    };
  }, []);

  useEffect(() => {
    const handleBeforeUnload = () => {
      cleanupUnfinishedInterview();
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, []);

  useEffect(() => {
    if (videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [isCameraRunning, hasInterviewStarted, phase]);

  const startCamera = async () => {
    setCameraError("");
    resetFaceVerification();

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }

      setIsCameraRunning(true);
    } catch (error) {
      console.error("Camera permission failed:", error);
      setCameraError("Camera and microphone permission failed. Please allow access to continue.");
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    setIsCameraRunning(false);
  };

  const handleStartInterview = async () => {
    if (isVerifyingFace || phase === "loadingQuestions") {
      return;
    }

    clearAutoAdvanceTimer();
    setQuestionGenerationError("");
    setAnswerError("");
    setStatusMessage("");

    try {
      setIsVerifyingFace(true);
      setStatusMessage("Verifying face...");
      const faceResult = isFaceVerified ? { match: true } : await verifyFaceWithAttempts();

      if (!faceResult?.match) {
        throw new Error("Face verification failed. Please try again.");
      }

      setPhase("loadingQuestions");
      setStatusMessage("Loading questions...");

      const response = await getInterviewQuestions(applicationSummary?.application_id);
      const loadedQuestions = Array.isArray(response.questions) ? response.questions.slice(0, 5) : [];

      if (loadedQuestions.length !== 5) {
        throw new Error("Interview must contain exactly 5 questions.");
      }

      setQuestions(loadedQuestions);
      setCurrentQuestionIndex(0);
      setHasInterviewStarted(true);
      setPhase("ready");
    } catch (error) {
      setQuestionGenerationError(error.message || "Could not start interview.");
      setPhase("error");
    } finally {
      setIsVerifyingFace(false);
    }
  };

  const verifyFaceWithAttempts = async () => {
    let lastResult = null;
    faceVerificationDoneRef.current = false;
    faceMatchCountRef.current = 0;
    setFaceMatchCount(0);
    setFaceStatus("verifying");
    setFaceError("");

    for (let attempt = 1; attempt <= 3; attempt += 1) {
      faceAttemptCountRef.current = attempt;
      setFaceAttemptCount(attempt);
      lastResult = await captureAndVerifyFaceFrame(attempt);

      if (lastResult?.match) {
        faceMatchCountRef.current = 1;
        setFaceMatchCount(1);
        faceVerificationDoneRef.current = true;
        setIsFaceVerified(true);
        setFaceStatus("passed");
        return lastResult;
      }
    }

    faceVerificationDoneRef.current = true;
    setIsFaceVerified(false);
    setFaceStatus("failed");
    setFaceError("Face verification failed. Please try again.");
    return lastResult || { match: false };
  };

  const handleStartRecordingAnswer = () => {
    if (answerState !== "idle" && answerState !== "error") {
      return;
    }

    void startAudioRecording();
  };

  const startAudioRecording = async () => {
    try {
      setAnswerState("idle");
      setAnswerError("");
      setStatusMessage("");

      if (lastAudioUrlRef.current) {
        URL.revokeObjectURL(lastAudioUrlRef.current);
        lastAudioUrlRef.current = null;
      }

      setLastAudioDebug(null);

      const audioStream = await getAudioRecordingStream();
      audioChunksRef.current = [];

      const recorder = new MediaRecorder(audioStream, getRecorderOptions());

      recorder.ondataavailable = (event) => {
        console.log("[Audio Debug] dataavailable size:", event.data?.size);

        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }

        console.log("[Audio Debug] chunks count:", audioChunksRef.current.length);
      };

      recorder.onstart = () => {
        console.log("[Audio Debug] Recording started");
        setAnswerState("recording");
        setStatusMessage("");
      };

      recorder.onerror = (event) => {
        console.error("[Audio Debug] Recorder error:", event);
        setAnswerError("Recording failed.");
        setAnswerState("error");
      };

      mediaRecorderRef.current = recorder;

      // Important: emits chunks every second so we can confirm audio is being captured.
      recorder.start(1000);
    } catch (error) {
      console.error("Audio recording failed:", error);
      setAnswerError(error.message || "Could not start recording.");
      setAnswerState("error");
    }
  };

  const handleStopAnswer = async () => {
    if (answerState !== "recording") {
      return;
    }

    setAnswerState("submitting");
    setStatusMessage("Preparing audio...");
    setAnswerError("");

    try {
      const audioBlob = await stopAudioRecording();

      console.log("[Audio Debug] Final blob:", audioBlob);
      console.log("[Audio Debug] Final blob size:", audioBlob.size);
      console.log("[Audio Debug] Final blob type:", audioBlob.type);

      if (!audioBlob || audioBlob.size === 0) {
        setAnswerError("No audio was recorded. Check microphone permission/input.");
        setAnswerState("error");
        return;
      }

      setStatusMessage("Submitting answer...");

      const response = await submitQuestionAudioAnswer(
        applicationSummary?.application_id,
        questions[currentQuestionIndex]?.id,
        audioBlob
      );

      setStatusMessage(response.message || "Answer submitted successfully.");
      setAnswerState("submitted");

      clearAutoAdvanceTimer();
      autoAdvanceTimerRef.current = window.setTimeout(() => {
        void goToNextQuestion();
      }, AUTO_ADVANCE_DELAY_MS);
    } catch (error) {
      console.error("[Audio Debug] Stop/submit failed:", error);
      setAnswerError(error.message || "Could not submit answer.");
      setAnswerState("error");
    }
  };

  const goToNextQuestion = async () => {
    clearAutoAdvanceTimer();

    if (currentQuestionIndex >= questions.length - 1) {
      try {
        await completeInterview(applicationSummary?.application_id);
        setPhase("completed");
        setStatusMessage("Interview submitted successfully.");
        stopRecorderTracks();
      } catch (error) {
        setAnswerError(error.message || "Could not complete interview.");
        setPhase("error");
      }
      return;
    }

    setCurrentQuestionIndex((index) => index + 1);
    setStatusMessage("");
    setAnswerState("idle");
    setPhase("ready");
  };

  const stopAudioRecording = () => {
    return new Promise((resolve, reject) => {
      const recorder = mediaRecorderRef.current;

      if (!recorder || recorder.state === "inactive") {
        reject(new Error("No active recording found."));
        return;
      }

      recorder.onstop = () => {
        const mimeType = recorder.mimeType || "audio/webm";
        const chunks = [...audioChunksRef.current];

        console.log("[Audio Debug] Recording stopped");
        console.log("[Audio Debug] Final chunks:", chunks);
        console.log("[Audio Debug] Final chunks count:", chunks.length);

        const audioBlob = new Blob(chunks, { type: mimeType });
        const audioUrl = URL.createObjectURL(audioBlob);

        if (lastAudioUrlRef.current) {
          URL.revokeObjectURL(lastAudioUrlRef.current);
        }

        lastAudioUrlRef.current = audioUrl;

        const filename = `test_recording_q${currentQuestionIndex + 1}_${Date.now()}.webm`;

        setLastAudioDebug({
          url: audioUrl,
          size: audioBlob.size,
          type: audioBlob.type || mimeType,
          chunks: chunks.length,
          filename,
        });

        console.log("[Audio Debug] Audio preview URL:", audioUrl);
        console.log("[Audio Debug] Download filename:", filename);

        mediaRecorderRef.current = null;
        stopRecorderTracks();
        resolve(audioBlob);
      };

      recorder.onerror = (event) => {
        console.error("[Audio Debug] Recorder stop error:", event);
        mediaRecorderRef.current = null;
        stopRecorderTracks();
        reject(new Error("Recording failed."));
      };

      recorder.requestData();
      recorder.stop();
    });
  };

  const getAudioRecordingStream = async () => {
    const stream = streamRef.current;
    const audioTracks = stream?.getAudioTracks?.() || [];

    if (audioTracks.length) {
      return new MediaStream(audioTracks);
    }

    if (recorderStreamRef.current?.getAudioTracks?.().length) {
      return recorderStreamRef.current;
    }

    const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recorderStreamRef.current = audioStream;
    return audioStream;
  };

  const stopRecorderTracks = () => {
    if (recorderStreamRef.current) {
      recorderStreamRef.current.getTracks().forEach((track) => track.stop());
      recorderStreamRef.current = null;
    }
  };

  const captureAndVerifyFaceFrame = async (attemptNumber = 1) => {
    if (
      isFaceVerified ||
      isFaceRequestInFlightRef.current
    ) {
      return { match: isFaceVerified };
    }

    isFaceRequestInFlightRef.current = true;
    setFaceStatus("verifying");
    setFaceError("");

    try {
      await ensureCameraForVerification();
      await waitForVideoFrame();

      const video = videoRef.current;
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
      const nextAttemptCount = attemptNumber;
      const nextMatchCount = result.match ? 1 : 0;

      faceAttemptCountRef.current = nextAttemptCount;
      faceMatchCountRef.current = nextMatchCount;

      setFaceAttemptCount(nextAttemptCount);
      setFaceMatchCount(nextMatchCount);
      setFaceScore(typeof result.score === "number" ? result.score : null);
      setFaceReferenceSource(result.reference_source || "");
      setFaceError(result.success === false ? getBackendMessage(result) : "");

      if (result.match) {
        return result;
      }

      return result;
    } catch (error) {
      console.error("Face verification failed:", error);
      setFaceError(error.message || "Face verification failed.");
      return { match: false, message: error.message || "Face verification failed." };
    } finally {
      isFaceRequestInFlightRef.current = false;
    }
  };

  const ensureCameraForVerification = async () => {
    if (streamRef.current) {
      return;
    }

    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    streamRef.current = stream;

    if (videoRef.current) {
      videoRef.current.srcObject = stream;
    }

    setIsCameraRunning(true);
  };

  const waitForVideoFrame = () => {
    return new Promise((resolve, reject) => {
      const startedAt = Date.now();

      const check = () => {
        const video = videoRef.current;

        if (video?.videoWidth && video?.videoHeight && video.readyState >= 2) {
          resolve();
          return;
        }

        if (Date.now() - startedAt > 3000) {
          reject(new Error("Camera preview is not ready yet."));
          return;
        }

        window.setTimeout(check, 100);
      };

      check();
    });
  };

  const resetFaceVerification = () => {
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

  const resetInterview = () => {
    clearAutoAdvanceTimer();
    stopRecorderTracks();
    setPhase("ready");
    setQuestions([]);
    setCurrentQuestionIndex(0);
    setStatusMessage("");
    setQuestionGenerationError("");
    setAnswerError("");
    setAnswerState("idle");
    setHasInterviewStarted(false);
  };

  const handleBackHome = () => {
    cleanupUnfinishedInterview();
    resetInterview();
    stopCamera();
    onBackHome();
  };

  const cleanupUnfinishedInterview = () => {
    if (!hasInterviewStartedRef.current || phaseRef.current === "completed") {
      return;
    }

    void cleanupInterview(applicationSummary?.application_id, { keepalive: true }).catch(() => {});
  };

  const clearAutoAdvanceTimer = () => {
    if (autoAdvanceTimerRef.current) {
      window.clearTimeout(autoAdvanceTimerRef.current);
      autoAdvanceTimerRef.current = null;
    }
  };

  const currentQuestion = questions[currentQuestionIndex];
  const faceStatusText = getFaceStatusText(faceStatus, isCameraRunning);

  return (
    <main className="interview-page">
      <section className={`interview-panel ${hasInterviewStarted ? "active" : "precheck"}`}>
        <button className="back-button" type="button" onClick={handleBackHome}>
          Back Home
        </button>

        {!hasInterviewStarted && (
          <PreInterviewView
            videoRef={videoRef}
            isCameraRunning={isCameraRunning}
            isFaceVerified={isFaceVerified}
            faceStatus={faceStatus}
            faceStatusText={faceStatusText}
            faceAttemptCount={faceAttemptCount}
            faceMatchCount={faceMatchCount}
            faceScore={faceScore}
            faceReferenceSource={faceReferenceSource}
            faceError={faceError}
            cameraError={cameraError}
            isVerifyingFace={isVerifyingFace}
            phase={phase}
            questionGenerationError={questionGenerationError}
            onStartCamera={startCamera}
            onStopCamera={stopCamera}
            onStartInterview={handleStartInterview}
          />
        )}

        {hasInterviewStarted && currentQuestion && phase !== "completed" && (
          <ActiveInterviewView
            videoRef={videoRef}
            isCameraRunning={isCameraRunning}
            question={currentQuestion}
            questionNumber={currentQuestionIndex + 1}
            totalQuestions={questions.length}
            phase={phase}
            answerState={answerState}
            statusMessage={statusMessage}
            answerError={answerError}
            lastAudioDebug={lastAudioDebug}
            onStartRecordingAnswer={handleStartRecordingAnswer}
            onStopAnswer={handleStopAnswer}
            onStopCamera={stopCamera}
          />
        )}

        {hasInterviewStarted && phase === "completed" && (
          <CompletionView statusMessage={statusMessage} onBackHome={handleBackHome} />
        )}
      </section>
    </main>
  );
}


function PreInterviewView({
  videoRef,
  isCameraRunning,
  isFaceVerified,
  faceStatus,
  faceStatusText,
  faceAttemptCount,
  faceMatchCount,
  faceScore,
  faceReferenceSource,
  faceError,
  cameraError,
  isVerifyingFace,
  phase,
  questionGenerationError,
  onStartCamera,
  onStopCamera,
  onStartInterview,
}) {
  return (
    <>
      <header className="interview-header">
        <p className="eyebrow">Interview</p>
        <h1>Interview Session</h1>
        <p>Complete face verification, then start the voice interview.</p>
      </header>

      <CameraPreview videoRef={videoRef} isCameraRunning={isCameraRunning} size="large" />

      <div className="camera-actions centered">
        <button className="camera-button start" type="button" onClick={onStartCamera} disabled={isCameraRunning}>
          Start Camera
        </button>
        <button className="camera-button stop" type="button" onClick={onStopCamera} disabled={!isCameraRunning}>
          Stop Camera
        </button>
      </div>

      {cameraError && <p className="error-message">{cameraError}</p>}

      <FaceStatusCard
        faceStatus={faceStatus}
        faceStatusText={faceStatusText}
        faceAttemptCount={faceAttemptCount}
        faceMatchCount={faceMatchCount}
        faceScore={faceScore}
        faceReferenceSource={faceReferenceSource}
        faceError={faceError}
      />

      <section className="start-interview-card">
        {isFaceVerified && <p className="verified-kicker">Face verification passed</p>}
        <h2>Ready to begin</h2>
        <p className="precheck-note">Start Interview will verify your face once and then load your questions.</p>
        <button
          className="start-interview-button"
          type="button"
          onClick={onStartInterview}
          disabled={isVerifyingFace || phase === "loadingQuestions"}
        >
          {isVerifyingFace ? "Verifying Face..." : phase === "loadingQuestions" ? "Preparing Interview..." : "Start Interview"}
        </button>

        {questionGenerationError && <p className="error-message">{questionGenerationError}</p>}
      </section>
    </>
  );
}


function ActiveInterviewView({
  videoRef,
  isCameraRunning,
  question,
  questionNumber,
  totalQuestions,
  phase,
  answerState,
  statusMessage,
  answerError,
  lastAudioDebug,
  onStartRecordingAnswer,
  onStopAnswer,
  onStopCamera,
}) {
  return (
    <section className="active-interview">
      <header className="active-question-header">
        <div className="question-progress-row">
          <p className="question-count">Question {questionNumber} of {totalQuestions}</p>
          <div className="question-meta">
            {question.category && <span>{question.category}</span>}
            {question.difficulty && <span>{question.difficulty}</span>}
          </div>
        </div>
        <h1>{question.question}</h1>
      </header>

      <div className="interview-workspace">
        <section className="voice-answer-panel">
          {(answerState === "idle" || answerState === "error") && (
            <>
              {answerState === "error" && <p className="answer-error">{answerError || "Could not record answer."}</p>}
              <button className="recording-btn start" type="button" onClick={onStartRecordingAnswer}>
                Start Recording
              </button>
            </>
          )}

          {answerState === "recording" && (
            <div className="recording-controls">
              <p className="recording-status" aria-live="polite">Recording...</p>
              <button className="recording-btn stop" type="button" onClick={onStopAnswer}>
                Stop Recording
              </button>
            </div>
          )}

          {answerState === "submitting" && <p className="submission-status">Submitting answer...</p>}
          {answerState === "submitted" && <p className="success-message">Answer submitted successfully.</p>}
          {statusMessage && !["recording", "submitted", "submitting"].includes(answerState) && (
            <p className="status-message">{statusMessage}</p>
          )}

          <AudioDebugPanel audioDebug={lastAudioDebug} />
        </section>

        <aside className="camera-mini-card">
          <CameraPreview videoRef={videoRef} isCameraRunning={isCameraRunning} size="small" />
          <button className="camera-button stop compact" type="button" onClick={onStopCamera} disabled>
            Camera locked during interview
          </button>
        </aside>
      </div>
    </section>
  );
}


function CompletionView({ statusMessage, onBackHome }) {
  return (
    <section className="interview-summary candidate-completion">
      <p className="verified-kicker">Complete</p>
      <h1>{statusMessage || "Interview submitted successfully."}</h1>
      <button className="start-interview-button" type="button" onClick={onBackHome}>
        Back Home
      </button>
    </section>
  );
}


function FaceStatusCard({
  faceStatus,
  faceStatusText,
  faceAttemptCount,
  faceMatchCount,
  faceScore,
  faceReferenceSource,
  faceError,
}) {
  return (
    <section className={`face-status ${faceStatus}`}>
      <p className="face-status-text">{faceStatusText}</p>
      <div className="face-details">
        <span>Attempts: {faceAttemptCount}/3</span>
        <span>Matches: {faceMatchCount}/1</span>
        <span>Score: {faceScore === null ? "--" : faceScore.toFixed(4)}</span>
        <span>Reference: {faceReferenceSource ? toTitleCase(faceReferenceSource) : "--"}</span>
      </div>
      {faceError && <p className="face-error">{faceError}</p>}
    </section>
  );
}


function AudioDebugPanel({ audioDebug }) {
  if (!audioDebug) {
    return null;
  }

  return (
    <div className="audio-debug-panel">
      <p>
        Last recording: {formatBytes(audioDebug.size)} | Chunks: {audioDebug.chunks} | Type: {audioDebug.type}
      </p>

      <audio controls src={audioDebug.url} />

      <a href={audioDebug.url} download={audioDebug.filename}>
        Download test recording
      </a>
    </div>
  );
}


function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) {
    return "0 B";
  }

  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}


function CameraPreview({ videoRef, isCameraRunning, size }) {
  return (
    <div className={`video-frame ${size === "small" ? "mini" : "large"}`}>
      <video className="video-preview" ref={videoRef} autoPlay playsInline muted />
      {!isCameraRunning && <p className="video-placeholder">Camera preview will appear here.</p>}
    </div>
  );
}


function getRecorderOptions() {
  if (window.MediaRecorder?.isTypeSupported?.("audio/webm;codecs=opus")) {
    return { mimeType: "audio/webm;codecs=opus" };
  }

  if (window.MediaRecorder?.isTypeSupported?.("audio/webm")) {
    return { mimeType: "audio/webm" };
  }

  return undefined;
}


function getFaceStatusText(faceStatus, isCameraRunning) {
  if (faceStatus === "passed") {
    return "Face verified successfully";
  }

  if (faceStatus === "failed") {
    return "Face verification failed. Please ensure your face is clearly visible.";
  }

  if (faceStatus === "verifying") {
    return "Verifying face...";
  }

  if (isCameraRunning) {
    return "Camera ready. Face verification will run once when you start interview.";
  }

  return "Start Interview will request camera access and verify your face once.";
}


function toTitleCase(value) {
  return String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}


function getBackendMessage(data) {
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