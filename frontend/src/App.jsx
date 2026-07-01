import { useEffect, useRef, useState } from "react";
import ResumeViewerPage from "./pages/ResumeViewerPage";
import AadhaarUploadPage from "./pages/AadhaarUploadPage.jsx";
import AtsScreeningPage from "./pages/AtsScreeningPage.jsx";
import CurrentJobsPage from "./pages/CurrentJobsPage.jsx";
import FaceVerificationPage from "./pages/FaceVerificationPage.jsx";
import HomePage from "./pages/HomePage.jsx";
import HRDashboardPage from "./pages/HRDashboardPage.jsx";
import HRHomePage from "./pages/HRHomePage.jsx";
import InterviewPage from "./pages/InterviewPage.jsx";
import JobApplicationsPage from "./pages/JobApplicationsPage.jsx";
import ConfigureInterviewPage from "./pages/ConfigureInterviewPage.jsx";
import QuestionBankPage from "./pages/QuestionBankPage.jsx";
import ShortlistedCandidatesPage from "./pages/ShortlistedCandidatesPage.jsx";
import StudentUploadPage from "./pages/StudentUploadPage.jsx";
import UploadResumesPage from "./pages/UploadResumePage.jsx";
import {
  getCandidateVerificationData,
  getVerificationStatus,
} from "./api/kycApi.js";
import { checkInterviewAccess } from "./api/interviewApi.js";
import AdminLoginPage from "./pages/AdminLoginPage.jsx";

function App() {
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
  const [interviewMode, setInterviewMode] = useState("generate");

  useEffect(() => {
    const stopOnUnload = () => {
      stopCandidateCamera();
    };

    window.addEventListener("beforeunload", stopOnUnload);

    return () => {
      window.removeEventListener("beforeunload", stopOnUnload);
      stopCandidateCamera();
    };
  }, []);

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

    setCandidateLoadingMessage(interviewMatch ? "Loading interview..." : "Loading candidate verification...");
    setCurrentPage("candidate-loading");

    const continueCandidateFlow = () => {
    if (verifyMatch) {
      getCandidateVerificationData(applicationId)
        .then((data) => {
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
      getVerificationStatus(applicationId)
        .then((data) => {
          if (!isAadhaarVerified(data.data)) {
            window.history.replaceState(null, "", `/verify/${encodeURIComponent(applicationId)}`);
            return getCandidateVerificationData(applicationId).then((candidateData) => {
              setApplicationSummary(candidateData.data);
              setCurrentPage("aadhaar");
            });
          }

          if (isFaceVerified(data.data)) {
            window.history.replaceState(null, "", `/interview/${encodeURIComponent(applicationId)}`);
            return getCandidateVerificationData(applicationId).then((candidateData) => {
              setApplicationSummary(candidateData.data);
              setCurrentPage("interview");
            });
          }

          return getCandidateVerificationData(applicationId).then((candidateData) => {
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

    getVerificationStatus(applicationId)
      .then((data) => {
        if (!isAadhaarVerified(data.data)) {
          window.history.replaceState(null, "", `/verify/${encodeURIComponent(applicationId)}`);
          return getCandidateVerificationData(applicationId).then((candidateData) => {
            setApplicationSummary(candidateData.data);
            setCurrentPage("aadhaar");
          });
        }

        if (!isFaceVerified(data.data)) {
          window.history.replaceState(null, "", `/face-verification/${encodeURIComponent(applicationId)}`);
          return getCandidateVerificationData(applicationId).then((candidateData) => {
            setApplicationSummary(candidateData.data);
            setCurrentPage("face-verification");
          });
        }

        return getCandidateVerificationData(applicationId).then((candidateData) => {
          setApplicationSummary(candidateData.data);
          setCurrentPage("interview");
        });
      })
      .catch((error) => {
        setLinkValidationError(error.message || "Interview link is invalid.");
        setCurrentPage("candidate-link-error");
      });
    };

    checkInterviewAccess(applicationId)
      .then((access) => {
        if (access.status === "allowed" || access.status === "in_progress") {
          continueCandidateFlow();
          return;
        }

        if (access.status === "too_early") {
          setLinkValidationError(access.message || "Please come back at the scheduled time.");
          setCurrentPage("candidate-waiting");
          return;
        }

        if (access.status === "completed") {
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
  }, []);

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
              `/face-verification/${encodeURIComponent(applicationSummary.application_id)}`
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
          setApplicationSummary((currentSummary) => ({
            ...(currentSummary || {}),
            ...(summary || {}),
            aadhaarVerified: true,
            aadhaar_verified: true,
            governmentIdVerified: true,
            government_id_verified: true,
            faceVerified: true,
            face_verified: true,
            verification_completed: true,
            verification_status: "verified",
          }));
          if (applicationSummary?.application_id) {
            window.history.replaceState(
              null,
              "",
              `/interview/${encodeURIComponent(applicationSummary.application_id)}`
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
          onConfigureInterview={(application, mode = "generate") => {
          setInterviewMode(mode);
          setSelectedInterviewApplication(application);
          window.history.replaceState(
              null,
              "",
              `/configure-interview/${encodeURIComponent(application.application_id)}`
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
        mode={interviewMode}
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


export default App;


function isAadhaarVerified(data) {
  const identity = data?.identityVerification || data?.identity_verification || {};
  return (
    data?.aadhaarVerified === true ||
    data?.aadhaar_verified === true ||
    data?.governmentIdVerified === true ||
    data?.government_id_verified === true ||
    identity?.isValidIndianGovId === true ||
    identity?.is_valid_indian_gov_id === true ||
    String(data?.verification_status || "").toLowerCase() === "aadhaar_passed" ||
    String(data?.verification_status || "").toLowerCase() === "government_id_passed" ||
    String(data?.verification_status || "").toLowerCase() === "identity_passed" ||
    String(data?.verificationStatus || "").toLowerCase() === "aadhaar_passed" ||
    String(data?.verificationStatus || "").toLowerCase() === "government_id_passed" ||
    String(data?.verificationStatus || "").toLowerCase() === "identity_passed" ||
    String(data?.verificationStatus || "").toLowerCase() === "verified" ||
    String(data?.verification_status || "").toLowerCase() === "verified"
  );
}


function isFaceVerified(data) {
  return (
    data?.faceVerified === true ||
    data?.face_verified === true ||
    data?.verification_completed === true ||
    String(data?.verificationStatus || "").toLowerCase() === "verified" ||
    String(data?.verification_status || "").toLowerCase() === "verified"
  );
}
