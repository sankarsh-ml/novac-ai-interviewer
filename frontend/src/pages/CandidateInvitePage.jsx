import { useCallback, useEffect, useState } from "react";

import { fetchCandidateInvite } from "../api/resumeApi.js";
import AadhaarUploadPage from "./AadhaarUploadPage.jsx";
import InterviewPage from "./InterviewPage.jsx";
import "../styles/CandidateInvitePage.css";


function CandidateInvitePage({ token, onBackHome }) {
  const [invite, setInvite] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadInvite = useCallback(async () => {
    if (!token) {
      setError("Invalid or expired interview link.");
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError("");
      const data = await fetchCandidateInvite(token);
      setInvite(data);
    } catch (apiError) {
      setInvite(null);
      setError(apiError.message || "Invalid or expired interview link.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void loadInvite();
  }, [loadInvite]);

  if (loading) {
    return (
      <CandidateShell>
        <h1>Loading interview link...</h1>
        <p>Please wait while we validate your invite.</p>
      </CandidateShell>
    );
  }

  if (error || !invite) {
    return (
      <CandidateShell>
        <h1>Invalid or expired interview link.</h1>
        <p>{error || "Please contact HR for a fresh interview link."}</p>
      </CandidateShell>
    );
  }

  const applicationSummary = {
    application_id: invite.application_id,
    resume_name: invite.candidate_name,
    file_name: invite.resume_file,
  };

  if (invite.next_step === "aadhaar") {
    return (
      <AadhaarUploadPage
        applicationSummary={applicationSummary}
        onBackHome={onBackHome}
        onVerified={() => {
          void loadInvite();
        }}
      />
    );
  }

  if (invite.next_step === "face") {
    return (
      <InterviewPage
        applicationSummary={applicationSummary}
        mode="face"
        onBackHome={onBackHome}
        onFaceVerified={() => {
          void loadInvite();
        }}
      />
    );
  }

  if (invite.next_step === "interview") {
    return (
      <InterviewPage
        applicationSummary={applicationSummary}
        initialFaceVerified={invite.face_verified}
        onBackHome={onBackHome}
        onCompleted={() => {
          void loadInvite();
        }}
      />
    );
  }

  return (
    <CandidateShell>
      <p className="verified-kicker">Complete</p>
      <h1>Submission Complete</h1>
      <p>Thank you. Your interview has been submitted successfully.</p>
    </CandidateShell>
  );
}


function CandidateShell({ children }) {
  return (
    <main className="candidate-invite-page">
      <section className="candidate-invite-panel">
        {children}
      </section>
    </main>
  );
}


export default CandidateInvitePage;
