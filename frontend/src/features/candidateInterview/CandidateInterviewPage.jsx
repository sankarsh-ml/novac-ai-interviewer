import { useEffect, useRef, useState } from "react";

import {
  captureLivenessReference,
  checkLivenessFrame,
  completeInterview,
  evaluateInterviewAnswer,
  quitInterview,
  quitInterviewWithBeacon,
  saveInterviewAnswer,
  sendInterviewHeartbeat,
  startInterview,
  transcribeInterviewAudio,
} from "../../services/interviewApi.js";
import "../../styles/InterviewPage.css";


function InterviewPage({ applicationSummary, cameraSession, onBackHome }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const audioStreamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const autoStartInFlightRef = useRef(false);
  const livenessTimeoutRef = useRef(null);
  const heartbeatIntervalRef = useRef(null);
  const isLivenessCheckingRef = useRef(false);
  const livenessReferenceReadyRef = useRef(false);
  const interviewActiveRef = useRef(false);
  const interviewCompletedRef = useRef(false);
  const [cameraError, setCameraError] = useState("");
  const [cameraStatus, setCameraStatus] = useState(cameraSession?.isCameraRunning ? "active" : "idle");
  const [isCameraRunning, setIsCameraRunning] = useState(Boolean(cameraSession?.isCameraRunning));
  const [isFaceVerified, setIsFaceVerified] = useState(false);
  const [isInterviewStarted, setIsInterviewStarted] = useState(false);
  const [isGeneratingQuestions, setIsGeneratingQuestions] = useState(false);
  const [questions, setQuestions] = useState([]);
  const [questionSource, setQuestionSource] = useState("");
  const [qwenWarning, setQwenWarning] = useState("");
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [currentTranscript, setCurrentTranscript] = useState("");
  const [currentAudioPath, setCurrentAudioPath] = useState("");
  const [answers, setAnswers] = useState({});
  const [transcripts, setTranscripts] = useState({});
  const [audioPaths, setAudioPaths] = useState({});
  const [evaluations, setEvaluations] = useState({});
  const [isSubmittingAnswer, setIsSubmittingAnswer] = useState(false);
  const [isPreparingRecording, setIsPreparingRecording] = useState(false);
  const [isRecordingAnswer, setIsRecordingAnswer] = useState(false);
  const [isTranscribingAnswer, setIsTranscribingAnswer] = useState(false);
  const [currentEvaluation, setCurrentEvaluation] = useState(null);
  const [hasSubmittedCurrentAnswer, setHasSubmittedCurrentAnswer] = useState(false);
  const [interviewCompleted, setInterviewCompleted] = useState(isInterviewCompleted(applicationSummary));
  const [questionGenerationError, setQuestionGenerationError] = useState("");
  const [hasAttemptedQuestionLoad, setHasAttemptedQuestionLoad] = useState(false);
  const [answerError, setAnswerError] = useState("");
  const [voiceError, setVoiceError] = useState("");
  const [completionError, setCompletionError] = useState("");
  const [livenessWarning, setLivenessWarning] = useState("");
  const [livenessState, setLivenessState] = useState("idle");
  const [isLivenessReferenceReady, setIsLivenessReferenceReady] = useState(false);
  const [livenessSummary, setLivenessSummary] = useState(getInitialLivenessSummary(applicationSummary));

  useEffect(() => {
    return () => {
      stopLivenessChecks();
      stopHeartbeat();
      stopCamera();
    };
  }, []);

  useEffect(() => {
    interviewActiveRef.current = isInterviewStarted;
  }, [isInterviewStarted]);

  useEffect(() => {
    interviewCompletedRef.current = interviewCompleted;
  }, [interviewCompleted]);

  useEffect(() => {
    livenessReferenceReadyRef.current = isLivenessReferenceReady;
  }, [isLivenessReferenceReady]);

  useEffect(() => {
    if (isInterviewCompleted(applicationSummary)) {
      setInterviewCompleted(true);
      setIsInterviewStarted(true);
      setHasAttemptedQuestionLoad(true);
      return;
    }

    if (!isCandidateFaceVerified(applicationSummary)) {
      return;
    }

    setIsFaceVerified(true);
    setLivenessSummary(getInitialLivenessSummary(applicationSummary));
  }, [applicationSummary]);

  useEffect(() => {
    const stream = getReusableCameraStream(cameraSession?.stream) || getReusableCameraStream(streamRef.current);

    if (!stream) {
      return;
    }

    attachCameraStream(stream, "shared-camera").catch((error) => {
      console.error("[Interview] Could not attach camera preview:", error);
      if (!hasActiveCamera()) {
        setCameraStatus("error");
        setCameraError("Camera access is required for the interview. Please allow camera permission and refresh.");
      }
    });
  }, [cameraSession?.stream, isInterviewStarted, interviewCompleted]);

  useEffect(() => {
    if (!isInterviewStarted || interviewCompleted || !applicationSummary?.application_id) {
      return;
    }

    const handleBeforeUnload = () => {
      quitInterviewWithBeacon(applicationSummary.application_id);
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [applicationSummary?.application_id, interviewCompleted, isInterviewStarted]);

  useEffect(() => {
    if (!isInterviewStarted || interviewCompleted || !applicationSummary?.application_id) {
      stopHeartbeat();
      return;
    }

    sendInterviewHeartbeat(applicationSummary.application_id).catch(() => {});
    heartbeatIntervalRef.current = window.setInterval(() => {
      sendInterviewHeartbeat(applicationSummary.application_id).catch(() => {});
    }, 20000);

    return () => {
      stopHeartbeat();
    };
  }, [applicationSummary?.application_id, interviewCompleted, isInterviewStarted]);

  useEffect(() => {
    if (!applicationSummary?.application_id || interviewCompleted) {
      return;
    }

    ensureCameraOn().catch(() => {});
  }, [applicationSummary?.application_id, interviewCompleted]);

  useEffect(() => {
    if (
      !isInterviewStarted ||
      interviewCompleted ||
      hasSubmittedCurrentAnswer ||
      !isLivenessReferenceReady ||
      !isCameraRunning ||
      !applicationSummary?.application_id
    ) {
      stopLivenessChecks();
      return;
    }

    scheduleNextLivenessCheck();

    return () => {
      stopLivenessChecks();
    };
  }, [
    applicationSummary?.application_id,
    currentQuestionIndex,
    hasSubmittedCurrentAnswer,
    interviewCompleted,
    isCameraRunning,
    isInterviewStarted,
    isLivenessReferenceReady,
  ]);

  async function attachCameraStream(stream, context) {
    const videoTracks = stream?.getVideoTracks?.() || [];
    console.log("[Interview] camera stream status:", {
      candidateId: applicationSummary?.application_id,
      context,
      streamExists: Boolean(stream),
      active: Boolean(stream?.active),
      videoTracks: videoTracks.length,
      videoTrackStates: videoTracks.map((track) => ({
        id: track.id,
        label: track.label,
        enabled: track.enabled,
        muted: track.muted,
        readyState: track.readyState,
      })),
    });

    if (!hasLiveVideoTrack(stream)) {
      throw new Error("Camera stream has no live video track.");
    }

    setCameraStatus("requesting");
    streamRef.current = stream;

    if (videoRef.current) {
      if (videoRef.current.srcObject !== stream) {
        videoRef.current.srcObject = stream;
      }

      await videoRef.current.play();
    }

    setIsCameraRunning(true);
    setCameraStatus("active");
    setCameraError("");
    return stream;
  }

  function stopAudioStream(audioStream = audioStreamRef.current) {
    if (!audioStream) {
      return;
    }

    audioStream.getTracks?.().forEach((track) => {
      if (track.kind === "audio") {
        track.stop();
      }
    });

    if (audioStreamRef.current === audioStream) {
      audioStreamRef.current = null;
    }
  }

  const ensureCameraOn = async () => {
    if (hasActiveCamera()) {
      setCameraStatus("active");
      setCameraError("");
      return streamRef.current || cameraSession?.stream || videoRef.current?.srcObject;
    }

    setCameraStatus("requesting");
    setCameraError("");

    try {
      const reusableStream = getReusableCameraStream(cameraSession?.stream) || getReusableCameraStream(streamRef.current);
      const stream = reusableStream || (
        cameraSession?.startCamera
          ? await cameraSession.startCamera()
          : await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      );

      if (!hasLiveVideoTrack(stream)) {
        throw new Error("Camera stream has no live video track.");
      }

      await attachCameraStream(stream, reusableStream ? "reused-camera" : "new-camera");
      return stream;

    } catch (error) {
      console.error("[Interview] Camera unavailable:", error);
      if (hasActiveCamera()) {
        setCameraStatus("active");
        setCameraError("");
        return streamRef.current || cameraSession?.stream || videoRef.current?.srcObject;
      }

      const denied = error?.name === "NotAllowedError" || error?.name === "PermissionDeniedError";
      setCameraStatus(denied ? "denied" : "error");
      setCameraError("Camera access is required for the interview. Please allow camera permission and refresh.");
      throw new Error("Camera access is required for the interview. Please allow camera permission and refresh.");
    }
  };

  const startCamera = ensureCameraOn;

  const stopCamera = () => {
    stopLivenessChecks();
    stopHeartbeat();
    stopActiveRecording();
    stopAudioStream();
    cameraSession?.stopCamera?.();
    streamRef.current = null;

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    setIsCameraRunning(false);
    setCameraStatus("idle");
  };

  const hasActiveCamera = () => (
    hasLiveVideoTrack(streamRef.current) ||
    hasLiveVideoTrack(cameraSession?.stream) ||
    hasLiveVideoTrack(videoRef.current?.srcObject)
  );

  const shouldShowCameraError = () => (
    Boolean(cameraError) &&
    ["denied", "error"].includes(cameraStatus) &&
    !hasActiveCamera()
  );

  const stopLivenessChecks = () => {
    if (livenessTimeoutRef.current) {
      window.clearTimeout(livenessTimeoutRef.current);
      livenessTimeoutRef.current = null;
    }
  };

  const stopHeartbeat = () => {
    if (heartbeatIntervalRef.current) {
      window.clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
  };

  const scheduleNextLivenessCheck = () => {
    stopLivenessChecks();

    if (!canRunLivenessCheck()) {
      return;
    }

    const delayMs = 10000 + Math.floor(Math.random() * 5001);
    livenessTimeoutRef.current = window.setTimeout(async () => {
      await runLivenessCheck("periodic", currentQuestionIndex + 1);

      if (
        canRunLivenessCheck() &&
        !hasSubmittedCurrentAnswer &&
        currentQuestionIndex < questions.length
      ) {
        scheduleNextLivenessCheck();
      }
    }, delayMs);
  };

  const canRunLivenessCheck = () => (
    Boolean(applicationSummary?.application_id) &&
    interviewActiveRef.current &&
    !interviewCompletedRef.current &&
    livenessReferenceReadyRef.current &&
    hasActiveCamera()
  );

  const captureBackendLivenessReference = async () => {
    setLivenessState("checking");
    setLivenessWarning("Checking face...");
    const images = await captureLivenessFrames();
    const response = await captureLivenessReference(applicationSummary?.application_id, {
      image: images[0] || "",
      images,
      check_type: "reference",
    });

    if (!response.ok) {
      setIsLivenessReferenceReady(false);
      livenessReferenceReadyRef.current = false;
      setLivenessState(response.event_type || response.status || "warning");
      setLivenessWarning(getLivenessMessage(response));
      if (response.liveness) {
        setLivenessSummary(response.liveness);
      }
      throw new Error(response.message || "Could not verify your face. Please keep one face visible on camera.");
    }

    setLivenessState("verified");
    setLivenessWarning("Face Verified");
    setIsLivenessReferenceReady(true);
    livenessReferenceReadyRef.current = true;

    if (response.liveness) {
      setLivenessSummary(response.liveness);
    }
  };

  const runLivenessCheck = async (checkType, questionIndex = currentQuestionIndex + 1) => {
    if (!applicationSummary?.application_id || !canRunLivenessCheck() || isLivenessCheckingRef.current) {
      return;
    }

    isLivenessCheckingRef.current = true;

    try {
      setLivenessState("checking");
      setLivenessWarning("Checking face...");
      const images = await captureLivenessFrames();
      const response = await checkLivenessFrame(applicationSummary.application_id, {
        image: images[0] || "",
        images,
        question_index: questionIndex,
        question_id: questions[currentQuestionIndex]?.id || "",
        check_type: checkType,
      });

      if (response.liveness) {
        setLivenessSummary(response.liveness);
      }

      setLivenessState(response.event_type || response.status || (response.ok ? "verified" : "warning"));
      setLivenessWarning(getLivenessMessage(response));
      return response;
    } catch (error) {
      console.error("[Interview] Liveness check failed:", error);
      setLivenessState("warning");
      setLivenessWarning(error.message || "Warning: Face check could not be completed.");
      return null;
    } finally {
      isLivenessCheckingRef.current = false;
    }
  };

  const captureLivenessFrames = async () => {
    await waitForVideoReady(videoRef.current);
    const frames = [];

    for (let index = 0; index < 3; index += 1) {
      frames.push(captureVideoFrame(videoRef.current));

      if (index < 2) {
        await delay(550);
      }
    }

    return frames;
  };

  const captureVideoFrame = (video) => {
    if (!video || video.readyState < 2 || !video.videoWidth || !video.videoHeight) {
      throw new Error("Camera is not ready for face check.");
    }

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");

    if (!context) {
      throw new Error("Could not capture camera frame.");
    }

    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.82);
  };

  const waitForVideoReady = async (video) => {
    const startedAt = Date.now();

    while (Date.now() - startedAt < 4000) {
      if (video?.readyState >= 2 && video.videoWidth > 0 && video.videoHeight > 0) {
        return;
      }

      await delay(100);
    }

    throw new Error("Camera is not ready for face check.");
  };

  const delay = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

  const getLivenessMessage = (response) => {
    if (response?.event_type === "face_match" || response?.status === "passed" || response?.status === "reference_set") {
      return "Face Verified";
    }

    if (response?.event_type === "multiple_faces_detected" || response?.status === "multiple_faces_detected") {
      return "Warning: Multiple faces detected";
    }

    if (response?.event_type === "identity_mismatch") {
      return "Suspicious: Different person detected";
    }

    if (response?.event_type === "no_face_detected" || response?.status === "no_face_detected") {
      return "Warning: Face not detected";
    }

    return response?.message || "Checking face...";
  };

  const getLivenessTone = () => {
    if (livenessState === "checking") {
      return "checking";
    }

    if (livenessState === "identity_mismatch" || livenessState === "suspicious") {
      return "suspicious";
    }

    if (
      livenessState === "no_face_detected" ||
      livenessState === "multiple_faces_detected" ||
      livenessState === "warning"
    ) {
      return "warning";
    }

    return "passed";
  };

  const resetInterviewState = () => {
    setIsInterviewStarted(false);
    setIsGeneratingQuestions(false);
    setQuestions([]);
    setQuestionSource("");
    setQwenWarning("");
    setCurrentQuestionIndex(0);
    setCurrentTranscript("");
    setCurrentAudioPath("");
    setAnswers({});
    setTranscripts({});
    setAudioPaths({});
    setEvaluations({});
    setIsSubmittingAnswer(false);
    setIsPreparingRecording(false);
    setIsRecordingAnswer(false);
    setIsTranscribingAnswer(false);
    setCurrentEvaluation(null);
    setHasSubmittedCurrentAnswer(false);
    setInterviewCompleted(false);
    setQuestionGenerationError("");
    setAnswerError("");
    setVoiceError("");
  };

  const handleStartInterview = async () => {
    setIsGeneratingQuestions(true);
    setQuestionGenerationError("");
    setQwenWarning("");

    try {
      console.log("[Interview] candidateId from route/state:", applicationSummary?.application_id);
      console.log("[Interview] verification check:", {
        aadhaarVerified: isCandidateAadhaarVerified(applicationSummary),
        faceVerified: isCandidateFaceVerified(applicationSummary),
      });
      const response = await startInterview(applicationSummary?.application_id);
      console.log("[Interview] question bank/start response:", response);

      if (
        response.status === "completed" ||
        response.interview_status === "completed" ||
        response.interviewStatus === "completed" ||
        response.interview_completed === true
      ) {
        setInterviewCompleted(true);
        setIsInterviewStarted(true);
        return;
      }

      const stream = getReusableCameraStream(cameraSession?.stream) || getReusableCameraStream(streamRef.current);
      if (stream) {
        await attachCameraStream(stream, "start-interview");
      } else {
        await ensureCameraOn();
      }
      await captureBackendLivenessReference();

      const loadedQuestions = normalizeInterviewQuestions(response.questions);
      console.log("[Interview] final questions array length:", loadedQuestions.length);

      if (!loadedQuestions.length) {
        throw new Error(response.message || "No question bank found for this role.");
      }

      setQuestions(loadedQuestions);
      setQuestionSource(response.source || response.question_source || "");
      setQwenWarning(response.qwen_warning || response.qwen_error || "");
      setCurrentQuestionIndex(0);
      setCurrentTranscript("");
      setCurrentAudioPath("");
      setCurrentEvaluation(null);
      setHasSubmittedCurrentAnswer(false);
      setInterviewCompleted(false);
      setIsInterviewStarted(true);
    } catch (error) {
      setQuestionGenerationError(error.message || "No question bank found for this role.");
      setIsInterviewStarted(false);
    } finally {
      setHasAttemptedQuestionLoad(true);
      setIsGeneratingQuestions(false);
    }
  };

  useEffect(() => {
    if (
      !applicationSummary?.application_id ||
      (isGovernmentIdRequired(applicationSummary) && !isCandidateAadhaarVerified(applicationSummary)) ||
      !isCandidateFaceVerified(applicationSummary) ||
      isInterviewStarted ||
      interviewCompleted ||
      isGeneratingQuestions ||
      hasAttemptedQuestionLoad
    ) {
      return;
    }

    if (autoStartInFlightRef.current) {
      return;
    }

    autoStartInFlightRef.current = true;
    handleStartInterview().finally(() => {
      autoStartInFlightRef.current = false;
    });
  }, [
    applicationSummary?.application_id,
    cameraSession?.stream,
    interviewCompleted,
    hasAttemptedQuestionLoad,
    isGeneratingQuestions,
    isInterviewStarted,
  ]);

  const handleSubmitAnswer = async () => {
    const question = questions[currentQuestionIndex];
    const isSubmittingFinalQuestion = currentQuestionIndex === questions.length - 1;

    if (!question || hasSubmittedCurrentAnswer) {
      return;
    }

    setIsSubmittingAnswer(true);
    setAnswerError("");
    setCompletionError("");

    try {
      await saveInterviewAnswer(applicationSummary?.application_id, {
        question_index: currentQuestionIndex + 1,
        question_id: question.id,
        question: question.question,
        expected_answer: question.expectedAnswer || "",
        candidate_answer: currentTranscript,
        score: null,
        feedback: null,
        status: "submitted",
        submitted_at: new Date().toISOString(),
      });
      await runLivenessCheck("before-submit");
      const response = await evaluateInterviewAnswer(
        applicationSummary?.application_id,
        question.id,
        currentTranscript,
        {
          transcript: currentTranscript,
          audioPath: currentAudioPath,
        }
      );

      setAnswers((currentAnswers) => ({
        ...currentAnswers,
        [question.id]: currentTranscript,
      }));
      setTranscripts((currentTranscripts) => ({
        ...currentTranscripts,
        [question.id]: currentTranscript,
      }));
      setAudioPaths((currentAudioPaths) => ({
        ...currentAudioPaths,
        [question.id]: currentAudioPath,
      }));
      setEvaluations((currentEvaluations) => ({
        ...currentEvaluations,
        [question.id]: response,
      }));
      setCurrentEvaluation(response);
      setHasSubmittedCurrentAnswer(true);

      if (isSubmittingFinalQuestion) {
        try {
          await completeInterview(applicationSummary?.application_id);
          setInterviewCompleted(true);
          stopCamera();
        } catch (error) {
          setCompletionError(error.message || "Could not complete interview.");
        }
      }
    } catch (error) {
      const message = error.message || "Could not evaluate answer.";
      setAnswerError(
        message.toLowerCase().includes("qwen grading failed")
          ? "Qwen grading failed. Please retry submission."
          : message
      );
    } finally {
      setIsSubmittingAnswer(false);
    }
  };

  const handleNextQuestion = () => {
    const nextIndex = currentQuestionIndex + 1;
    const nextQuestion = questions[nextIndex];

    stopActiveRecording();
    setCurrentQuestionIndex(nextIndex);
    setCurrentTranscript(transcripts[nextQuestion?.id] || "");
    setCurrentAudioPath(audioPaths[nextQuestion?.id] || "");
    setCurrentEvaluation(nextQuestion ? evaluations[nextQuestion.id] || null : null);
    setHasSubmittedCurrentAnswer(Boolean(nextQuestion && evaluations[nextQuestion.id]));
    setAnswerError("");
    setVoiceError("");
  };

  const handleStartRecording = async () => {
    setVoiceError("");
    setCurrentTranscript("");
    setCurrentAudioPath("");

    if (!window.MediaRecorder) {
      setVoiceError("Audio recording is not supported in this browser.");
      return;
    }

    if (isPreparingRecording || isRecordingAnswer || isTranscribingAnswer) {
      return;
    }

    setIsPreparingRecording(true);

    try {
      await runLivenessCheck("start_recording", currentQuestionIndex + 1);
      const recordingQuestionIndex = currentQuestionIndex;
      const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioStreamRef.current = audioStream;
      const audioTracks = audioStream.getAudioTracks();
      const [audioTrack] = audioTracks;

      console.log("[Interview] audio stream created:", {
        candidateId: applicationSummary?.application_id,
        audioTracks: audioTracks.length,
        audioTrack: audioTrack
          ? {
              id: audioTrack.id,
              label: audioTrack.label,
              enabled: audioTrack.enabled,
              muted: audioTrack.muted,
              readyState: audioTrack.readyState,
            }
          : null,
      });

      if (!audioTrack || audioTrack.readyState !== "live") {
        stopAudioStream(audioStream);
        setVoiceError("Microphone is not available. Please allow microphone access and try again.");
        setIsPreparingRecording(false);
        return;
      }

      const recorderOptions = getRecorderOptions();
      const recorder = new MediaRecorder(audioStream, recorderOptions);
      audioChunksRef.current = [];
      mediaRecorderRef.current = recorder;

      console.log("[Interview] MediaRecorder prepared:", {
        candidateId: applicationSummary?.application_id,
        requestedMimeType: recorderOptions.mimeType || "",
        recorderMimeType: recorder.mimeType || "",
        stateBeforeStart: recorder.state,
      });

      recorder.ondataavailable = (event) => {
        if (event.data?.size) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onerror = (event) => {
        console.error("[Interview] MediaRecorder error:", event.error || event);
        setVoiceError("Could not start recording. Please allow microphone access and try again.");
      };

      recorder.onstop = async () => {
        const chunks = audioChunksRef.current;
        audioChunksRef.current = [];
        mediaRecorderRef.current = null;
        stopAudioStream(audioStream);
        setIsPreparingRecording(false);
        setIsRecordingAnswer(false);

        if (!chunks.length) {
          setVoiceError("No audio captured. Please record again.");
          return;
        }

        const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });

        console.log("[Interview] recorded blob:", {
          candidateId: applicationSummary?.application_id,
          questionIndex: recordingQuestionIndex,
          size: blob.size,
          type: blob.type,
        });

        if (!blob.size) {
          setVoiceError("No audio captured. Please record again.");
          return;
        }

        setIsTranscribingAnswer(true);

        try {
          const filename = `answer_${applicationSummary?.application_id}_${recordingQuestionIndex}.webm`;
          const response = await transcribeInterviewAudio(applicationSummary?.application_id, blob, filename);
          console.log("[Interview] Whisper response:", response);
          const transcript = response.transcript || "";
          const audioPath = response.audioPath || response.audio_path || "";

          if (!transcript.trim()) {
            throw new Error("Could not transcribe answer. Please record again.");
          }

          setCurrentTranscript(transcript);
          setCurrentAudioPath(audioPath);
        } catch (error) {
          setCurrentTranscript("");
          setCurrentAudioPath("");
          setVoiceError(error.message || "Could not transcribe answer. Please record again.");
        } finally {
          setIsTranscribingAnswer(false);
        }
      };

      if (recorder.state !== "inactive") {
        throw new Error(`Recorder is not ready. Current state: ${recorder.state}`);
      }

      recorder.start();
      console.log("[Interview] MediaRecorder start success:", {
        candidateId: applicationSummary?.application_id,
        state: recorder.state,
      });
      setIsPreparingRecording(false);
      setIsRecordingAnswer(true);
    } catch (error) {
      console.error("[Interview] MediaRecorder start failed:", error);
      stopAudioStream();
      mediaRecorderRef.current = null;
      setVoiceError("Could not start recording. Please allow microphone access and try again.");
      setIsPreparingRecording(false);
      setIsRecordingAnswer(false);
    }
  };

  const handleStopRecording = () => {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  };

  const stopActiveRecording = () => {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
      return;
    }

    mediaRecorderRef.current = null;
    setIsPreparingRecording(false);
    setIsRecordingAnswer(false);
    stopAudioStream();
  };

  const handleFinishInterview = async () => {
    setCompletionError("");

    try {
      await completeInterview(applicationSummary?.application_id);
      setInterviewCompleted(true);
      stopCamera();
    } catch (error) {
      setCompletionError(error.message || "Could not complete interview.");
    }
  };

  const handleBackHome = async () => {
    if (isInterviewStarted && !interviewCompleted) {
      try {
        await quitInterview(applicationSummary?.application_id);
      } catch (error) {
        console.error("Could not mark partial interview:", error);
      }
    }

    stopCamera();
    onBackHome();
  };

  const currentQuestion = questions[currentQuestionIndex];
  const isFinalQuestion = currentQuestionIndex === questions.length - 1;
  const sourceText = getQuestionSourceText(questionSource);

  if (!applicationSummary) {
    return (
      <main className="interview-page">
        <section className="interview-panel precheck">
          <header className="interview-header">
            <p className="eyebrow">Interview</p>
            <h1>Loading interview...</h1>
            <p>Please wait while we load candidate details.</p>
          </header>
        </section>
      </main>
    );
  }

  return (
    <main className="interview-page">
      <section className={`interview-panel ${isInterviewStarted ? "active" : "precheck"}`}>
        {!interviewCompleted && (
          <button className="back-button" type="button" onClick={handleBackHome}>
            Back Home
          </button>
        )}

        {!isInterviewStarted && (
          <PreInterviewView
            videoRef={videoRef}
            isCameraRunning={isCameraRunning}
            isFaceVerified={isFaceVerified}
            cameraError={shouldShowCameraError() ? cameraError : ""}
            cameraStatus={cameraStatus}
            isGeneratingQuestions={isGeneratingQuestions}
            questionGenerationError={questionGenerationError}
            onStartCamera={startCamera}
            onStopCamera={stopCamera}
            onStartInterview={handleStartInterview}
          />
        )}

        {isInterviewStarted && !interviewCompleted && currentQuestion && (
          <ActiveInterviewView
            videoRef={videoRef}
            isCameraRunning={isCameraRunning}
            sourceText={sourceText}
            question={currentQuestion}
            questionNumber={currentQuestionIndex + 1}
            totalQuestions={questions.length}
            currentTranscript={currentTranscript}
            currentEvaluation={currentEvaluation}
            answerError={answerError}
            voiceError={voiceError}
            isSubmittingAnswer={isSubmittingAnswer}
            isPreparingRecording={isPreparingRecording}
            isRecordingAnswer={isRecordingAnswer}
            isTranscribingAnswer={isTranscribingAnswer}
            hasSubmittedCurrentAnswer={hasSubmittedCurrentAnswer}
            isFinalQuestion={isFinalQuestion}
            onStartRecording={handleStartRecording}
            onStopRecording={handleStopRecording}
            onSubmitAnswer={handleSubmitAnswer}
            onNextQuestion={handleNextQuestion}
            onFinishInterview={handleFinishInterview}
            completionError={completionError}
          cameraError={shouldShowCameraError() ? cameraError : ""}
          onEnableCamera={ensureCameraOn}
          livenessWarning={livenessWarning}
          livenessTone={getLivenessTone()}
          livenessSummary={livenessSummary}
        />
        )}

        {isInterviewStarted && interviewCompleted && (
          <InterviewSummary />
        )}
      </section>
    </main>
  );
}


function PreInterviewView({
  videoRef,
  isCameraRunning,
  isFaceVerified,
  cameraError,
  cameraStatus,
  isGeneratingQuestions,
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
        <p>Start your camera before beginning. Voice recording will use your microphone.</p>
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

      {!isFaceVerified && (
        <section className="interview-placeholder">
          <p>Face verification is required before the interview can begin.</p>
        </section>
      )}

      {isFaceVerified && (
        <section className="start-interview-card">
          <p className="verified-kicker">Face verification passed</p>
          <h2>Ready to begin</h2>
          <p>Your camera will remain visible during the interview. Questions are generated only after you start.</p>
          <button
            className="start-interview-button"
            type="button"
            onClick={onStartInterview}
            disabled={!isCameraRunning || isGeneratingQuestions}
          >
          {isGeneratingQuestions ? "Starting interview..." : "Start Interview"}
          </button>
          {isGeneratingQuestions && !cameraError && (
            <p className="submission-success">{cameraStatus === "active" ? "Verifying face..." : "Starting interview..."}</p>
          )}
          {questionGenerationError && <p className="error-message">{questionGenerationError}</p>}
        </section>
      )}
    </>
  );
}


function ActiveInterviewView({
  videoRef,
  isCameraRunning,
  sourceText,
  question,
  questionNumber,
  totalQuestions,
  currentTranscript,
  currentEvaluation,
  answerError,
  voiceError,
  isSubmittingAnswer,
  isPreparingRecording,
  isRecordingAnswer,
  isTranscribingAnswer,
  hasSubmittedCurrentAnswer,
  isFinalQuestion,
  onStartRecording,
  onStopRecording,
  onSubmitAnswer,
  onNextQuestion,
  onFinishInterview,
  completionError,
  cameraError,
  onEnableCamera,
  livenessWarning,
  livenessTone,
  livenessSummary,
}) {
  return (
    <section className="active-interview">
      <header className="active-question-header">
        <div className="question-progress-row">
          <p className="question-count">Question {questionNumber} of {totalQuestions}</p>
          <div className="question-meta">
            <span>{question.category}</span>
            <span>{question.difficulty}</span>
          </div>
        </div>
        <h1>{question.question}</h1>
        {question.expected_focus && (
          <p className="expected-focus">Expected focus: {question.expected_focus}</p>
        )}
        <p className="question-source">{sourceText}</p>
      </header>

      <div className="interview-workspace">
        <section className="answer-panel">
          <div className="voice-card">
            <div>
              <strong>Voice answer</strong>
              <p>
                {isRecordingAnswer
                  ? "Recording in progress..."
                  : isTranscribingAnswer
                    ? "Transcribing with Whisper..."
                    : currentTranscript
                      ? "Transcript is ready. Manual typing is disabled for interview integrity."
                      : "Record your answer. Manual typing is disabled for interview integrity."}
              </p>
            </div>
            <div className="voice-actions">
              <button
                className="record-button"
                type="button"
                onClick={onStartRecording}
                disabled={isPreparingRecording || isRecordingAnswer || isTranscribingAnswer || hasSubmittedCurrentAnswer}
              >
                {isPreparingRecording ? "Preparing..." : "Start Recording"}
              </button>
              <button
                className="stop-record-button"
                type="button"
                onClick={onStopRecording}
                disabled={!isRecordingAnswer}
              >
                Stop
              </button>
            </div>
          </div>
          {voiceError && <p className="answer-error">{voiceError}</p>}

          <label className="answer-label" htmlFor={`answer-${question.id}`}>
            Transcript
          </label>
          <textarea
            id={`answer-${question.id}`}
            className="answer-input active-answer-input"
            value={currentTranscript}
            placeholder="Your transcribed answer will appear here after recording."
            rows={9}
            readOnly
          />
          <button
            className="submit-answer-button"
            type="button"
            onClick={onSubmitAnswer}
            disabled={!currentTranscript.trim() || isSubmittingAnswer || isRecordingAnswer || isTranscribingAnswer || hasSubmittedCurrentAnswer}
          >
            {isSubmittingAnswer ? "Submitting..." : "Submit Answer"}
          </button>

          {answerError && <p className="answer-error">{answerError}</p>}
          {currentEvaluation && <p className="submission-success">Answer submitted successfully.</p>}

          {hasSubmittedCurrentAnswer && !isFinalQuestion && (
            <button className="next-question-button" type="button" onClick={onNextQuestion}>
              Next Question
            </button>
          )}

          {hasSubmittedCurrentAnswer && isFinalQuestion && (
            <button className="finish-interview-button" type="button" onClick={onFinishInterview}>
              Finish Interview
            </button>
          )}
          {completionError && <p className="answer-error">{completionError}</p>}
        </section>

        <aside className="camera-mini-card">
          <CameraPreview videoRef={videoRef} isCameraRunning={isCameraRunning} size="small" />
          {!isCameraRunning && (
            <button className="camera-button start compact" type="button" onClick={onEnableCamera}>
              Enable Camera
            </button>
          )}
          {cameraError && <p className="answer-error">{cameraError}</p>}
          <LivenessPanel warning={livenessWarning} tone={livenessTone} summary={livenessSummary} />
        </aside>
      </div>
    </section>
  );
}


function LivenessPanel({ warning, tone, summary }) {
  const status = String(tone || summary?.status || "passed");
  return (
    <section className={`liveness-panel ${status}`}>
      <strong>Liveness / Identity</strong>
      <span>{formatLivenessStatus(status)}</span>
      <p>{warning || "Same-person checks are running while your camera stays on."}</p>
      <small>Warnings: {Number(summary?.total_warnings || 0)}</small>
    </section>
  );
}


function InterviewSummary() {
  return (
    <section className="interview-summary">
      <h1>Interview Over</h1>
      <p>Thank you. Your interview has been submitted successfully.</p>
    </section>
  );
}


function CameraPreview({ videoRef, isCameraRunning, size }) {
  return (
    <div className={`video-frame ${size === "small" ? "mini" : "large"}`}>
      <video className="video-preview" ref={videoRef} autoPlay playsInline muted />
      {!isCameraRunning && <p className="video-placeholder">Camera is not active.</p>}
    </div>
  );
}


function getQuestionSourceText(source) {
  if (source === "question_bank") {
    return "Question Bank";
  }

  if (source === "qwen") {
    return "Generated by Qwen";
  }

  return "Prepared by fallback engine";
}


function normalizeInterviewQuestions(value) {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item, index) => {
      if (!item || typeof item !== "object") {
        return null;
      }

      const question = String(
        item.question ||
          item.questionText ||
          item.text ||
          ""
      ).trim();

      if (!question) {
        return null;
      }

      return {
        id: String(item.id || item.question_id || `q${index + 1}`),
        question,
        expectedAnswer: String(
          item.expectedAnswer ||
            item.expected_answer ||
            item.answer ||
            ""
        ).trim(),
        difficulty: String(item.difficulty || "Medium").trim() || "Medium",
        skill: String(item.skill || item.category || item.topic || "").trim(),
        category: String(item.category || item.skill || item.topic || "Question Bank").trim(),
      };
    })
    .filter(Boolean);
}


function isCandidateAadhaarVerified(candidate) {
  const identity = candidate?.identityVerification || candidate?.identity_verification || {};
  return (
    candidate?.aadhaarVerified === true ||
    candidate?.aadhaar_verified === true ||
    candidate?.governmentIdVerified === true ||
    candidate?.government_id_verified === true ||
    identity?.isValidIndianGovId === true ||
    identity?.is_valid_indian_gov_id === true ||
    String(candidate?.verificationStatus || "").toLowerCase() === "aadhaar_passed" ||
    String(candidate?.verificationStatus || "").toLowerCase() === "government_id_passed" ||
    String(candidate?.verificationStatus || "").toLowerCase() === "identity_passed" ||
    String(candidate?.verificationStatus || "").toLowerCase() === "verified" ||
    String(candidate?.verification_status || "").toLowerCase() === "aadhaar_passed" ||
    String(candidate?.verification_status || "").toLowerCase() === "government_id_passed" ||
    String(candidate?.verification_status || "").toLowerCase() === "identity_passed" ||
    String(candidate?.verification_status || "").toLowerCase() === "verified"
  );
}


function isGovernmentIdRequired(candidate) {
  const identityConfig = candidate?.identityConfig || candidate?.identity_config || {};
  return identityConfig.requireGovernmentId !== false;
}


function isCandidateFaceVerified(candidate) {
  return (
    candidate?.faceVerified === true ||
    candidate?.face_verified === true ||
    candidate?.verification_completed === true ||
    String(candidate?.verificationStatus || "").toLowerCase() === "verified" ||
    String(candidate?.verification_status || "").toLowerCase() === "verified"
  );
}


function isInterviewCompleted(candidate) {
  return (
    candidate?.interview_completed === true ||
    String(candidate?.interview_status || "").toLowerCase() === "completed" ||
    String(candidate?.interviewStatus || "").toLowerCase() === "completed"
  );
}


function getReusableCameraStream(stream) {
  return hasLiveVideoTrack(stream) ? stream : null;
}


function hasLiveVideoTrack(stream) {
  const videoTracks = stream?.getVideoTracks?.() || [];
  return Boolean(stream?.active && videoTracks.some((track) => track.readyState === "live"));
}


function getRecorderOptions() {
  const preferredTypes = [
    "audio/webm;codecs=opus",
    "audio/webm",
  ];

  const mimeType = preferredTypes.find((type) => (
    window.MediaRecorder?.isTypeSupported?.(type)
      ? window.MediaRecorder.isTypeSupported(type)
      : false
  ));
  return mimeType ? { mimeType } : {};
}


function getInitialLivenessSummary(candidate) {
  return candidate?.liveness || {
    status: "passed",
    total_warnings: 0,
    no_face_count: 0,
    multiple_face_count: 0,
    identity_mismatch_count: 0,
    events: [],
  };
}


function formatLivenessStatus(status) {
  if (status === "checking") {
    return "Checking face...";
  }

  if (status === "suspicious") {
    return "Suspicious";
  }

  if (status === "warning") {
    return "Warning";
  }

  return "Passed";
}


export default InterviewPage;
