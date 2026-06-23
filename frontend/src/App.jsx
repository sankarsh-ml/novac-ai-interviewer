import { useState } from "react";

import AadhaarUploadPage from "./pages/AadhaarUploadPage.jsx";
import AtsScreeningPage from "./pages/AtsScreeningPage.jsx";
import HomePage from "./pages/HomePage.jsx";
import HRDashboardPage from "./pages/HRDashboardPage.jsx";
import InterviewPage from "./pages/InterviewPage.jsx";
import StudentUploadPage from "./pages/StudentUploadPage.jsx";
import HRHomePage from "./pages/HRHomePage.jsx";
import CurrentJobsPage from "./pages/CurrentJobsPage.jsx";
import JobApplicationsPage from "./pages/JobApplicationsPage.jsx";

function App() {
  const [currentPage, setCurrentPage] = useState("home");
  const [applicationSummary, setApplicationSummary] = useState(null);
  const [aadhaarSummary, setAadhaarSummary] = useState(null);
  const [selectedJob,setSelectedJob] =useState(null);
  const handleUploadSuccess = (summary) => {
    setApplicationSummary(summary);
    setCurrentPage("ats");
  };

  const handleBackHome = () => {
    setApplicationSummary(null);
    setAadhaarSummary(null);
    setCurrentPage("home");
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
        onBackHome={handleBackHome}
      />
    );
  }

  if (currentPage === "admin") {
    return (
      <HRHomePage
        onBack={handleBackHome}
        onOpenAddJob={() =>
          setCurrentPage("add-job")
        }
        onOpenCurrentJobs={() =>
          setCurrentPage("current-jobs")
        }
      />
    );
  }

  if (currentPage === "add-job") {
    return (
      <HRDashboardPage
        onBack={() =>
          setCurrentPage("admin")
        }
      />
    );
  }

  if (currentPage === "current-jobs") {
  return (
    <CurrentJobsPage
      onBack={() =>
        setCurrentPage("admin")
      }
      onViewApplications={(job) => {
        setSelectedJob(job);
        setCurrentPage("job-applications");
      }}
    />
  );
}

  if (currentPage === "job-applications") {
    return (
      <JobApplicationsPage
        job={selectedJob}
        onBack={() =>
          setCurrentPage("current-jobs")
        }
      />
    );
  }
  
  return (
    <HomePage
      onOpenStudent={() => setCurrentPage("student")}
      onOpenAdmin={() => setCurrentPage("admin")}
    />
  );
}


export default App;
