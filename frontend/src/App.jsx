import { useState } from "react";

import CandidateInvitePage from "./pages/CandidateInvitePage.jsx";
import HRDashboardPage from "./pages/HRDashboardPage.jsx";
import WhisperTestPage from "./pages/WhisperTestPage.jsx";


function App() {
  const candidateInviteToken = getCandidateInviteToken();
  const [currentPage, setCurrentPage] = useState(() => {
    if (candidateInviteToken) {
      return "candidate-invite";
    }

    if (window.location.pathname === "/test-whisper") {
      return "whisper-test";
    }

    return "admin";
  });

  const handleBackHome = () => {
    window.history.pushState({}, "", "/");
    setCurrentPage("admin");
  }

  if (currentPage === "admin") {
    return <HRDashboardPage />;
  }

  if (currentPage === "candidate-invite") {
    return <CandidateInvitePage token={candidateInviteToken} onBackHome={handleBackHome} />;
  }

  if (currentPage === "whisper-test") {
    return <WhisperTestPage onBack={handleBackHome} />;
  }

  return <HRDashboardPage />;
}


function getCandidateInviteToken() {
  const match = window.location.pathname.match(/^\/candidate\/invite\/([^/]+)\/?$/);
  return match ? decodeURIComponent(match[1]) : "";
}


export default App;
