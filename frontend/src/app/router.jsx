import { useEffect, useRef, useState } from "react";
import ResumeViewerPage from "@presentation/pages/ResumeViewerPage";
import AadhaarUploadPage from "@presentation/pages/AadhaarUploadPage.jsx";
import AtsScreeningPage from "@presentation/pages/AtsScreeningPage.jsx";
import CurrentJobsPage from "@presentation/pages/CurrentJobsPage.jsx";
import FaceVerificationPage from "@presentation/components/identity/FaceVerification.jsx";
import HomePage from "@presentation/pages/HomePage.jsx";
import HRDashboardPage from "@presentation/pages/HRDashboardPage.jsx";
import HRHomePage from "@presentation/pages/HRHomePage.jsx";
import InterviewPage from "@presentation/pages/InterviewPage.jsx";
import JobApplicationsPage from "@presentation/pages/JobApplicationsPage.jsx";
import ConfigureInterviewPage from "@presentation/pages/ConfigureInterviewPage.jsx";
import QuestionBankPage from "@presentation/pages/QuestionBankPage.jsx";
import ShortlistedCandidatesPage from "@presentation/pages/ShortlistedCandidatesPage.jsx";
import StudentUploadPage from "@presentation/pages/StudentUploadPage.jsx";
import UploadResumesPage from "@presentation/pages/UploadResumePage.jsx";
import {
  fetchCandidateVerificationData,
  fetchVerificationStatus,
} from "@application/useCases/identityUseCases.js";
import { checkInterviewAccess } from "@application/useCases/interviewUseCases.js";
import {
  isFaceVerified,
  isGovernmentIdRequired,
  isGovernmentIdVerified,
  isResumePhotoMissingFallback,
  shouldUseResumePhotoVerification,
} from "@domain/rules/identityRules.js";
import { useDependencies } from "@presentation/hooks/useDependencies.js";
import AdminLoginPage from "@presentation/pages/AdminLoginPage.jsx";

function App() {
  const { identityRepository, interviewRepository } = useDependencies();
  const [currentPage, setCurrentPage] = useState("home");
  const [applicationSummary, setApplicationSummary] = useState(null);
  const [aadhaarSummary, setAadhaarSummary] = useState(null);
  const [selectedJob, setSelectedJob] = useState(null);
  const [selectedInterviewApplication, setSelectedInterviewApplication] = useState(null);
  const [questionBankMode, setQuestionBankMode] = useState("manage");
  const [linkValidationError, setLinkValidationError] = useState("");
  const [candidateLoadingMessage, setCandidateLoadingMessage] = useState("Loading candidate verification...");
  const [cameraStream, setCameraStream] = useState(null);
  const [isCameraRunning, setIsCameraRunning] = useState(false);
  const cameraStreamRef = useRef(null);
  const [selectedResume, setSelectedResume] = useState(null);

  useEffect(() => {
    const stopOnUnload = () => {
      stopCandidateCamera();
    };

    window.addEventListener("beforeunload", stopOnUnload);

    return () => {
      window.removeEventListener("beforeunload", stopOnUnload);
      stopCandidateCamera();
    };
  }, [identityRepository, interviewRepository]);

  useEffect(() => {
    const configureMatch = window.location.pathname.match(/^\/configure-interview\/([^/]+)$/);
    const verifyMatch = window.location.pathname.match(/^\/verify\/([^/]+)$/);
    const faceMatch = window.location.pathname.match(/^\/face-verification\/([^/]+)$/);
    const interviewMatch = window.location.pathname.match(/^\/interview\/([^/]+)$/);

    if (configureMatch) {
      setSelectedInterviewApplication({
        application_id: decodeURIComponent(configureMatch[1]),
      });
      setCurrentPage("configure-interview");
      return;
    }

    if (!verifyMatch && !faceMatch && !interviewMatch) {
      return;
    }

    const applicationId = decodeURIComponent((verifyMatch || faceMatch || interviewMatch)[1]);
    const attemptToken = new URLSearchParams(window.location.search).get("attempt") || "";
    const candidatePath = (segment) => withAttemptQuery(`/${segment}/${encodeURIComponent(applicationId)}`, attemptToken);

    setCandidateLoadingMessage(interviewMatch ? "Loading interview..." : "Loading candidate verification...");
    setCurrentPage("candidate-loading");

    const continueCandidateFlow = () => {
    if (verifyMatch) {
      fetchCandidateVerificationData(identityRepository, applicationId)
        .then((data) => {
          if (shouldUseResumePhotoVerification(data.data)) {
            window.history.replaceState(null, "", candidatePath("face-verification"));
            setApplicationSummary(data.data);
            setCurrentPage("face-verification");
            return;
          }

          setApplicationSummary(data.data);
          setCurrentPage("aadhaar");
        })
        .catch((error) => {
          setLinkValidationError(error.message || "Candidate verification link is invalid.");
          setCurrentPage("candidate-link-error");
        });
      return;
    }

    if (faceMatch) {
      fetchVerificationStatus(identityRepository, applicationId)
        .then((data) => {
          if (isResumePhotoMissingFallback(data.data)) {
            window.history.replaceState(null, "", candidatePath("verify"));
            return fetchCandidateVerificationData(identityRepository, applicationId).then((candidateData) => {
              setApplicationSummary(candidateData.data);
              setCurrentPage("aadhaar");
            });
          }

          if (isGovernmentIdRequired(data.data) && !isGovernmentIdVerified(data.data)) {
            window.history.replaceState(null, "", candidatePath("verify"));
            return fetchCandidateVerificationData(identityRepository, applicationId).then((candidateData) => {
              setApplicationSummary(candidateData.data);
              setCurrentPage("aadhaar");
            });
          }

          if (isFaceVerified(data.data)) {
            window.history.replaceState(null, "", candidatePath("interview"));
            return fetchCandidateVerificationData(identityRepository, applicationId).then((candidateData) => {
              setApplicationSummary(candidateData.data);
              setCurrentPage("interview");
            });
          }

          return fetchCandidateVerificationData(identityRepository, applicationId).then((candidateData) => {
            setApplicationSummary(candidateData.data);
            setCurrentPage("face-verification");
          });
        })
        .catch((error) => {
          setLinkValidationError(error.message || "Face verification link is invalid.");
          setCurrentPage("candidate-link-error");
        });
      return;
    }

    fetchVerificationStatus(identityRepository, applicationId)
      .then((data) => {
        if (isResumePhotoMissingFallback(data.data)) {
          window.history.replaceState(null, "", candidatePath("verify"));
          return fetchCandidateVerificationData(identityRepository, applicationId).then((candidateData) => {
            setApplicationSummary(candidateData.data);
            setCurrentPage("aadhaar");
          });
        }

        if (isGovernmentIdRequired(data.data) && !isGovernmentIdVerified(data.data)) {
          window.history.replaceState(null, "", candidatePath("verify"));
          return fetchCandidateVerificationData(identityRepository, applicationId).then((candidateData) => {
            setApplicationSummary(candidateData.data);
            setCurrentPage("aadhaar");
          });
        }

        if (!isFaceVerified(data.data)) {
          window.history.replaceState(null, "", candidatePath("face-verification"));
          return fetchCandidateVerificationData(identityRepository, applicationId).then((candidateData) => {
            setApplicationSummary(candidateData.data);
            setCurrentPage("face-verification");
          });
        }

        return fetchCandidateVerificationData(identityRepository, applicationId).then((candidateData) => {
          setApplicationSummary(candidateData.data);
          setCurrentPage("interview");
        });
      })
      .catch((error) => {
        setLinkValidationError(error.message || "Interview link is invalid.");
        setCurrentPage("candidate-link-error");
      });
    };

    checkInterviewAccess(interviewRepository, applicationId, attemptToken)
      .then((access) => {
        if (access.status === "allowed" || access.status === "not_started" || access.status === "in_progress") {
          continueCandidateFlow();
          return;
        }

        if (access.status === "too_early") {
          setLinkValidationError(access.message || "Please come back at the scheduled time.");
          setCurrentPage("candidate-waiting");
          return;
        }

        if (access.status === "complete" || access.status === "completed") {
          setLinkValidationError(access.message || "Interview already completed.");
          setCurrentPage("candidate-link-error");
          return;
        }

        setLinkValidationError(access.message || "Set a proper interview date and time.");
        setCurrentPage("candidate-link-error");
      })
      .catch((error) => {
        setLinkValidationError(error.message || "Interview schedule could not be verified.");
        setCurrentPage("candidate-link-error");
      });
  }, [identityRepository, interviewRepository]);

  const handleUploadSuccess = (summary) => {
    setApplicationSummary(summary);
    setCurrentPage("ats");
  };

  const handleBackHome = () => {
    stopCandidateCamera();
    setApplicationSummary(null);
    setAadhaarSummary(null);
    setCurrentPage("home");
  };

  const startCandidateCamera = async () => {
    if (cameraStreamRef.current?.active) {
      setCameraStream(cameraStreamRef.current);
      setIsCameraRunning(true);
      return cameraStreamRef.current;
    }

    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    cameraStreamRef.current = stream;
    setCameraStream(stream);
    setIsCameraRunning(true);
    return stream;
  };

  const stopCandidateCamera = () => {
    if (cameraStreamRef.current) {
      cameraStreamRef.current.getTracks().forEach((track) => track.stop());
      cameraStreamRef.current = null;
    }

    setCameraStream(null);
    setIsCameraRunning(false);
  };

  const cameraSession = {
    stream: cameraStream,
    isCameraRunning,
    startCamera: startCandidateCamera,
    stopCamera: stopCandidateCamera,
  };

  if (currentPage === "student") {
    return <StudentUploadPage onBack={handleBackHome} onUploadSuccess={handleUploadSuccess} />;
  }

  if (currentPage === "ats") {
    return (
      <AtsScreeningPage
        applicationSummary={applicationSummary}
        onBackHome={handleBackHome}
        onPassed={() => setCurrentPage("aadhaar")}
      />
    );
  }

  if (currentPage === "aadhaar") {
    return (
      <AadhaarUploadPage
        applicationSummary={applicationSummary}
        onBackHome={handleBackHome}
        onVerified={(summary) => {
          setAadhaarSummary(summary);
          setApplicationSummary((currentSummary) => ({
            ...(currentSummary || {}),
            aadhaarVerified: true,
            aadhaar_verified: true,
            governmentIdVerified: true,
            government_id_verified: true,
            verification_status: "government_id_passed",
          }));
          if (applicationSummary?.application_id) {
            window.history.replaceState(
              null,
              "",
              withAttemptQuery(`/face-verification/${encodeURIComponent(applicationSummary.application_id)}`)
            );
          }
          setCurrentPage("face-verification");
        }}
      />
    );
  }

  if (currentPage === "face-verification") {
    return (
      <FaceVerificationPage
        applicationSummary={applicationSummary}
        cameraSession={cameraSession}
        onBackHome={handleBackHome}
        onVerified={(summary) => {
          const governmentIdRequired = isGovernmentIdRequired(applicationSummary);
          setApplicationSummary((currentSummary) => ({
            ...(currentSummary || {}),
            ...(summary || {}),
            aadhaarVerified: governmentIdRequired,
            aadhaar_verified: governmentIdRequired,
            governmentIdVerified: governmentIdRequired,
            government_id_verified: governmentIdRequired,
            faceVerified: true,
            face_verified: true,
            verification_completed: true,
            verification_status: "verified",
          }));
          if (applicationSummary?.application_id) {
            window.history.replaceState(
              null,
              "",
              withAttemptQuery(`/interview/${encodeURIComponent(applicationSummary.application_id)}`)
            );
          }
          setCurrentPage("interview");
        }}
      />
    );
  }

  if (currentPage === "interview") {
    return (
      <InterviewPage
        applicationSummary={applicationSummary}
        aadhaarSummary={aadhaarSummary}
        cameraSession={cameraSession}
        onBackHome={handleBackHome}
      />
    );
  }

  if (currentPage === "login") {
    return (
      <AdminLoginPage
        onLoginSuccess={() => setCurrentPage("admin")}
        onBack={handleBackHome}
      />
    );
  }

  if (currentPage === "admin") {
    return (
      <HRHomePage
        onBack={handleBackHome}
        onOpenAddJob={() => setCurrentPage("add-job")}
        onOpenCurrentJobs={() => setCurrentPage("current-jobs")}
      />
    );
  }

  if (currentPage === "add-job") {
    return <HRDashboardPage onBack={() => setCurrentPage("admin")} />;
  }

  if (currentPage === "current-jobs") {
    return (
      <CurrentJobsPage
        onBack={() => setCurrentPage("admin")}
        onViewApplications={(job) => {
          setSelectedJob(job);
          setCurrentPage("job-applications");
        }}
        onUploadResumes={(job) => {
          setSelectedJob(job);
          setCurrentPage("upload-resumes");
        }}
        onQuestionBank={(job) => {
          setSelectedJob(job);
          setQuestionBankMode("manage");
          setCurrentPage("question-bank");
        }}
        onViewQuestionBank={(job) => {
          setSelectedJob(job);
          setQuestionBankMode("view");
          setCurrentPage("question-bank");
        }}
      />
    );
  }

  if (currentPage === "upload-resumes") {
    return <UploadResumesPage job={selectedJob} onBack={() => setCurrentPage("current-jobs")} />;
  }

  if (currentPage === "question-bank") {
    return (
      <QuestionBankPage
        job={selectedJob}
        onBack={() => setCurrentPage("current-jobs")}
        readOnly={questionBankMode === "view"}
      />
    );
  }

  if (currentPage === "job-applications") {
    return (
      <JobApplicationsPage
          job={selectedJob}
          onBack={() => setCurrentPage("current-jobs")}
          onViewShortlisted={(job) => {
                setSelectedJob(job);
                setCurrentPage("shortlisted");
            }}
          onViewResume={(application) => {
            setSelectedResume(application);
            setCurrentPage("resume");
              }}
        />
    );
  }

  if (currentPage === "shortlisted") {
    return (
      <ShortlistedCandidatesPage
          job={selectedJob}
          onBack={() => setCurrentPage("job-applications")}
          onConfigureInterview={(application, options = {}) => {
            setSelectedInterviewApplication(application);
            const queryParams = new URLSearchParams();

            if (options.mode) {
              queryParams.set("mode", options.mode);
            }

            const jobId = application.job_id || application.jobId || selectedJob?.id || selectedJob?.jobId || "";
            const interviewId = application.active_attempt_id || application.interview_token || application.currentInterviewId || application.interviewId || "";

            if (jobId) {
              queryParams.set("jobId", jobId);
            }

            if (interviewId) {
              queryParams.set("interviewId", interviewId);
            }

            const queryString = queryParams.toString();
            window.history.replaceState(
              null,
              "",
              `/configure-interview/${encodeURIComponent(application.application_id)}${queryString ? `?${queryString}` : ""}`
            );
            setCurrentPage("configure-interview");
          }}
        />
    );
  }

  if (currentPage === "configure-interview") {
    return (
      <ConfigureInterviewPage
        applicationId={selectedInterviewApplication?.application_id}
        onBack={() => {
          window.history.replaceState(null, "", "/");
          setCurrentPage(selectedJob ? "shortlisted" : "current-jobs");
        }}
      />
    );
  }

  if (currentPage === "candidate-loading") {
    return (
      <main className="home-page">
        <section className="home-content">
          <h1>{candidateLoadingMessage}</h1>
        </section>
      </main>
    );
  }

  if (currentPage === "candidate-link-error") {
    return (
      <main className="home-page">
        <section className="home-content">
          <h1>Candidate link unavailable</h1>
          <p className="subtitle">{linkValidationError}</p>
        </section>
      </main>
    );
  }

  if (currentPage === "resume") {
    return (
      <ResumeViewerPage
        application={selectedResume}
        onBack={() => setCurrentPage("job-applications")}
      />
    );
  }

  if (currentPage === "candidate-waiting") {
    return (
      <main className="home-page">
        <section className="home-content">
          <h1>Interview scheduled</h1>
          <p className="subtitle">{linkValidationError}</p>
        </section>
      </main>
    );
  }

  return (
    <HomePage
    onOpenAdmin={() => setCurrentPage("login")}
    />
  );
}


function withAttemptQuery(path, attemptToken = "") {
  const token = attemptToken || new URLSearchParams(window.location.search).get("attempt") || "";
  return token ? `${path}?attempt=${encodeURIComponent(token)}` : path;
}


export default App;
