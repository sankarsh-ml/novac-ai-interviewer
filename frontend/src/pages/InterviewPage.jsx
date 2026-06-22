import { useEffect, useRef, useState } from "react";

import {
  evaluateInterviewAnswer,
  getInterviewQuestions,
  verifyFaceFrame,
} from "../api/interviewApi.js";
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
  const [isCameraRunning, setIsCameraRunning] = useState(false);
  const [faceStatus, setFaceStatus] = useState("idle");
  const [faceScore, setFaceScore] = useState(null);
  const [faceMatchCount, setFaceMatchCount] = useState(0);
  const [faceAttemptCount, setFaceAttemptCount] = useState(0);
  const [isFaceVerified, setIsFaceVerified] = useState(false);
  const [faceReferenceSource, setFaceReferenceSource] = useState("");
  const [faceError, setFaceError] = useState("");
  const [isInterviewStarted, setIsInterviewStarted] = useState(false);
  const [isGeneratingQuestions, setIsGeneratingQuestions] = useState(false);
  const [questions, setQuestions] = useState([]);
  const [questionSource, setQuestionSource] = useState("");
  const [qwenWarning, setQwenWarning] = useState("");
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [currentAnswer, setCurrentAnswer] = useState("");
  const [answers, setAnswers] = useState({});
  const [evaluations, setEvaluations] = useState({});
  const [isSubmittingAnswer, setIsSubmittingAnswer] = useState(false);
  const [currentEvaluation, setCurrentEvaluation] = useState(null);
  const [hasSubmittedCurrentAnswer, setHasSubmittedCurrentAnswer] = useState(false);
  const [interviewCompleted, setInterviewCompleted] = useState(false);
  const [questionGenerationError, setQuestionGenerationError] = useState("");
  const [answerError, setAnswerError] = useState("");

  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, []);

  useEffect(() => {
    if (videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [isInterviewStarted, interviewCompleted, isCameraRunning]);

  useEffect(() => {
    if (!isCameraRunning || isFaceVerified) {
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
  }, [isCameraRunning, isFaceVerified, applicationSummary?.application_id]);

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

    setIsCameraRunning(false);
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
    resetInterviewState();
  };

  const resetInterviewState = () => {
    setIsInterviewStarted(false);
    setIsGeneratingQuestions(false);
    setQuestions([]);
    setQuestionSource("");
    setQwenWarning("");
    setCurrentQuestionIndex(0);
    setCurrentAnswer("");
    setAnswers({});
    setEvaluations({});
    setIsSubmittingAnswer(false);
    setCurrentEvaluation(null);
    setHasSubmittedCurrentAnswer(false);
    setInterviewCompleted(false);
    setQuestionGenerationError("");
    setAnswerError("");
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

  const handleStartInterview = async () => {
    setIsGeneratingQuestions(true);
    setQuestionGenerationError("");
    setQwenWarning("");

    try {
      const response = await getInterviewQuestions(applicationSummary?.application_id);
      const loadedQuestions = Array.isArray(response.questions) ? response.questions : [];

      if (!loadedQuestions.length) {
        throw new Error("No interview questions were returned.");
      }

      setQuestions(loadedQuestions);
      setQuestionSource(response.source || "");
      setQwenWarning(response.qwen_warning || response.qwen_error || "");
      setCurrentQuestionIndex(0);
      setCurrentAnswer("");
      setCurrentEvaluation(null);
      setHasSubmittedCurrentAnswer(false);
      setInterviewCompleted(false);
      setIsInterviewStarted(true);
    } catch (error) {
      setQuestionGenerationError(error.message || "Could not start interview.");
    } finally {
      setIsGeneratingQuestions(false);
    }
  };

  const handleSubmitAnswer = async () => {
    const question = questions[currentQuestionIndex];

    if (!question || hasSubmittedCurrentAnswer) {
      return;
    }

    setIsSubmittingAnswer(true);
    setAnswerError("");

    try {
      const evaluation = await evaluateInterviewAnswer(
        applicationSummary?.application_id,
        question.id,
        currentAnswer
      );

      setAnswers((currentAnswers) => ({
        ...currentAnswers,
        [question.id]: currentAnswer,
      }));
      setEvaluations((currentEvaluations) => ({
        ...currentEvaluations,
        [question.id]: evaluation,
      }));
      setCurrentEvaluation(evaluation);
      setHasSubmittedCurrentAnswer(true);
    } catch (error) {
      setAnswerError(error.message || "Could not evaluate answer.");
    } finally {
      setIsSubmittingAnswer(false);
    }
  };

  const handleNextQuestion = () => {
    const nextIndex = currentQuestionIndex + 1;
    const nextQuestion = questions[nextIndex];

    setCurrentQuestionIndex(nextIndex);
    setCurrentAnswer(answers[nextQuestion?.id] || "");
    setCurrentEvaluation(nextQuestion ? evaluations[nextQuestion.id] || null : null);
    setHasSubmittedCurrentAnswer(Boolean(nextQuestion && evaluations[nextQuestion.id]));
    setAnswerError("");
  };

  const handleFinishInterview = () => {
    setInterviewCompleted(true);
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

    if (isCameraRunning) {
      return "Verifying face...";
    }

    return "Start camera to verify face.";
  })();
  const currentQuestion = questions[currentQuestionIndex];
  const isFinalQuestion = currentQuestionIndex === questions.length - 1;
  const sourceText = questionSource === "qwen" ? "Generated by Qwen" : "Generated by fallback engine";

  return (
    <main className="interview-page">
      <section className={`interview-panel ${isInterviewStarted ? "active" : "precheck"}`}>
        <button className="back-button" type="button" onClick={handleBackHome}>
          Back Home
        </button>

        {!isInterviewStarted && (
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
            faceScore={faceScore}
            faceReferenceSource={faceReferenceSource}
            sourceText={sourceText}
            qwenWarning={qwenWarning}
            question={currentQuestion}
            questionNumber={currentQuestionIndex + 1}
            totalQuestions={questions.length}
            currentAnswer={currentAnswer}
            currentEvaluation={currentEvaluation}
            answerError={answerError}
            isSubmittingAnswer={isSubmittingAnswer}
            hasSubmittedCurrentAnswer={hasSubmittedCurrentAnswer}
            isFinalQuestion={isFinalQuestion}
            onAnswerChange={setCurrentAnswer}
            onSubmitAnswer={handleSubmitAnswer}
            onNextQuestion={handleNextQuestion}
            onFinishInterview={handleFinishInterview}
            onStopCamera={stopCamera}
          />
        )}

        {isInterviewStarted && interviewCompleted && (
          <InterviewSummary
            questions={questions}
            evaluations={evaluations}
            sourceText={sourceText}
            onBackHome={handleBackHome}
          />
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
        <p>Please complete face verification before starting the interview.</p>
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
            disabled={isGeneratingQuestions}
          >
            {isGeneratingQuestions ? "Preparing Interview..." : "Start Interview"}
          </button>
          {questionGenerationError && <p className="error-message">{questionGenerationError}</p>}
        </section>
      )}
    </>
  );
}


function ActiveInterviewView({
  videoRef,
  isCameraRunning,
  faceScore,
  faceReferenceSource,
  sourceText,
  qwenWarning,
  question,
  questionNumber,
  totalQuestions,
  currentAnswer,
  currentEvaluation,
  answerError,
  isSubmittingAnswer,
  hasSubmittedCurrentAnswer,
  isFinalQuestion,
  onAnswerChange,
  onSubmitAnswer,
  onNextQuestion,
  onFinishInterview,
  onStopCamera,
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
        {qwenWarning && <p className="qwen-warning">{qwenWarning}</p>}
      </header>

      <div className="interview-workspace">
        <section className="answer-panel">
          <label className="answer-label" htmlFor={`answer-${question.id}`}>
            Candidate answer
          </label>
          <textarea
            id={`answer-${question.id}`}
            className="answer-input active-answer-input"
            value={currentAnswer}
            onChange={(event) => onAnswerChange(event.target.value)}
            placeholder="Type your answer here..."
            rows={9}
            disabled={hasSubmittedCurrentAnswer}
          />
          <button
            className="submit-answer-button"
            type="button"
            onClick={onSubmitAnswer}
            disabled={!currentAnswer.trim() || isSubmittingAnswer || hasSubmittedCurrentAnswer}
          >
            {isSubmittingAnswer ? "Evaluating..." : "Submit Answer"}
          </button>

          {answerError && <p className="answer-error">{answerError}</p>}
          {currentEvaluation && <EvaluationResult evaluation={currentEvaluation} />}

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
        </section>

        <aside className="camera-mini-card">
          <CameraPreview videoRef={videoRef} isCameraRunning={isCameraRunning} size="small" />
          <div className="face-mini-status">
            <strong>Face verified</strong>
            <span>Score: {faceScore === null ? "--" : faceScore.toFixed(4)}</span>
            <span>Reference: {faceReferenceSource ? toTitleCase(faceReferenceSource) : "--"}</span>
          </div>
          <button className="camera-button stop compact" type="button" onClick={onStopCamera} disabled={!isCameraRunning}>
            Stop Camera
          </button>
        </aside>
      </div>
    </section>
  );
}


function InterviewSummary({ questions, evaluations, sourceText, onBackHome }) {
  const rows = questions.map((question, index) => ({
    question,
    index,
    evaluation: evaluations[question.id],
  }));
  const answeredRows = rows.filter((row) => row.evaluation);
  const averageScore = calculateAverageScore(answeredRows.map((row) => row.evaluation?.score));
  const resultLabel = getResultLabel(averageScore);
  const finalFeedback = getFinalFeedback(answeredRows);

  return (
    <section className="interview-summary">
      <p className="question-source">{sourceText}</p>
      <h1>Interview Completed</h1>
      <div className="summary-stats">
        <SummaryStat label="Answered" value={`${answeredRows.length}/${questions.length}`} />
        <SummaryStat label="Average score" value={`${averageScore}/10`} />
        <SummaryStat label="Result" value={resultLabel} />
      </div>

      <div className="score-table">
        {rows.map(({ question, index, evaluation }) => (
          <article className="score-row" key={question.id}>
            <span>Q{index + 1}</span>
            <div>
              <strong>{question.category}</strong>
              <p>{question.question}</p>
            </div>
            <b>{evaluation?.score ?? 0}/10</b>
          </article>
        ))}
      </div>

      {finalFeedback && (
        <section className="final-feedback">
          <strong>Final feedback</strong>
          <p>{finalFeedback}</p>
        </section>
      )}

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
        <span>Attempts: {faceAttemptCount}/5</span>
        <span>Matches: {faceMatchCount}/3</span>
        <span>Score: {faceScore === null ? "--" : faceScore.toFixed(4)}</span>
        <span>Reference: {faceReferenceSource ? toTitleCase(faceReferenceSource) : "--"}</span>
      </div>
      {faceError && <p className="face-error">{faceError}</p>}
    </section>
  );
}


function CameraPreview({ videoRef, isCameraRunning, size }) {
  return (
    <div className={`video-frame ${size === "small" ? "mini" : "large"}`}>
      <video className="video-preview" ref={videoRef} autoPlay playsInline muted />
      {!isCameraRunning && <p className="video-placeholder">Camera preview will appear here.</p>}
    </div>
  );
}


function EvaluationResult({ evaluation }) {
  return (
    <section className={`evaluation-result ${evaluation.success ? "success" : "skipped"}`}>
      <div className="evaluation-score-grid">
        <ScoreItem label="Final score" value={evaluation.score} />
        <ScoreItem label="Relevance" value={evaluation.relevance_score} />
        <ScoreItem label="Technical" value={evaluation.technical_score} />
        <ScoreItem label="Depth" value={evaluation.depth_score} />
        <ScoreItem label="Clarity" value={evaluation.clarity_score} />
      </div>

      {evaluation.message && <p className="evaluation-message">{evaluation.message}</p>}
      {evaluation.feedback && <p className="evaluation-feedback">{evaluation.feedback}</p>}

      <EvaluationList title="Strengths" items={evaluation.strengths} />
      <EvaluationList title="Weaknesses" items={evaluation.weaknesses} />

      {evaluation.follow_up_question && (
        <p className="follow-up">
          <strong>Follow-up:</strong> {evaluation.follow_up_question}
        </p>
      )}
    </section>
  );
}


function ScoreItem({ label, value }) {
  if (value === undefined || value === null) {
    return null;
  }

  return (
    <div className="evaluation-score">
      <span>{label}</span>
      <strong>{value}/10</strong>
    </div>
  );
}


function EvaluationList({ title, items }) {
  if (!items?.length) {
    return null;
  }

  return (
    <div className="evaluation-list">
      <strong>{title}</strong>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}


function SummaryStat({ label, value }) {
  return (
    <article className="summary-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}


function calculateAverageScore(scores) {
  const numericScores = scores
    .map((score) => Number(score))
    .filter((score) => Number.isFinite(score));

  if (!numericScores.length) {
    return 0;
  }

  const average = numericScores.reduce((total, score) => total + score, 0) / numericScores.length;
  return Number(average.toFixed(1));
}


function getResultLabel(averageScore) {
  if (averageScore >= 8) {
    return "Strong candidate";
  }

  if (averageScore >= 6) {
    return "Moderate candidate";
  }

  return "Needs improvement";
}


function getFinalFeedback(rows) {
  const feedback = rows
    .map((row) => row.evaluation?.feedback)
    .filter(Boolean);

  return feedback[feedback.length - 1] || "";
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
