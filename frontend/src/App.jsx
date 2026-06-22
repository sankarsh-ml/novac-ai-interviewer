import { useState } from "react";

import AadhaarUploadPage from "./pages/AadhaarUploadPage.jsx";
import AtsScreeningPage from "./pages/AtsScreeningPage.jsx";
import HomePage from "./pages/HomePage.jsx";
import HRDashboardPage from "./pages/HRDashboardPage.jsx";
import InterviewPage from "./pages/InterviewPage.jsx";
import StudentUploadPage from "./pages/StudentUploadPage.jsx";


function App() {
  const [currentPage, setCurrentPage] = useState("home");
  const [applicationSummary, setApplicationSummary] = useState(null);
  const [aadhaarSummary, setAadhaarSummary] = useState(null);

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
    return <HRDashboardPage onBack={handleBackHome} />;
  }

  return (
    <HomePage
      onOpenStudent={() => setCurrentPage("student")}
      onOpenAdmin={() => setCurrentPage("admin")}
    />
  );
}


export default App;
