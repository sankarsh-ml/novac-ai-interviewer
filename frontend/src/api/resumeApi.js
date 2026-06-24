const API_BASE_URL = "http://127.0.0.1:8000";


export async function uploadResume(file, jobId = "") {
  const formData = new FormData();
  formData.append("file", file);

  if (jobId) {
    formData.append("job_id", jobId);
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/resume/upload`, {
      method: "POST",
      body: formData,
    });

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      console.error("Resume upload failed:", data);
      throw new Error(data?.detail || data?.message || "Resume upload failed");
    }

    return data;
  } catch (error) {
    console.error("Resume API request error:", error);
    if (error instanceof TypeError) {
      throw new Error("Could not connect to backend. Make sure FastAPI is running on port 8000.");
    }
    throw error;
  }
}


export async function submitAtsDecision(applicationId, decision) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/ats/${applicationId}/decision`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ decision }),
    });

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      console.error("ATS decision failed:", data);
      throw new Error(data?.detail || data?.message || "ATS decision failed");
    }

    return data;
  } catch (error) {
    console.error("ATS API request error:", error);
    throw error;
  }
}


export async function scoreResume(applicationId) {
  const response = await fetch(`${API_BASE_URL}/api/ats/score/${encodeURIComponent(applicationId)}`);
  const data = await response.json().catch(() => null);

  if (!response.ok || data?.success === false) {
    throw new Error(data?.detail || data?.message || "ATS scoring failed");
  }

  return data;
}


export async function fetchApplications() {
  const response = await fetch(`${API_BASE_URL}/api/hr/applications`);
  const data = await response.json().catch(() => null);

  if (!response.ok || data?.success === false) {
    throw new Error(data?.detail || data?.message || "Could not load applications");
  }

  return data.applications || [];
}

export async function fetchInterviewCandidates() {
  const response = await fetch(`${API_BASE_URL}/api/hr/interview-candidates`);
  const data = await response.json().catch(() => null);

  if (!response.ok || data?.success === false) {
    throw new Error(data?.detail || data?.message || "Could not load interview candidates");
  }

  return data.candidates || [];
}


export async function deleteInterviewCandidate(applicationId) {
  const response = await fetch(
    `${API_BASE_URL}/api/hr/interview-candidates/${encodeURIComponent(applicationId)}`,
    {
      method: "DELETE",
    }
  );
  const data = await response.json().catch(() => null);

  if (!response.ok || data?.success === false) {
    throw new Error(data?.detail || data?.message || "Could not delete candidate record");
  }

  return data;
}


export async function acceptApplication(applicationId) {
  const response = await fetch(
    `${API_BASE_URL}/api/hr/applications/${encodeURIComponent(applicationId)}/accept`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        frontend_base_url: window.location.origin,
      }),
    }
  );
  const data = await response.json().catch(() => null);

  if (!response.ok || data?.success === false) {
    throw new Error(data?.detail || data?.message || "Could not accept resume");
  }

  return data;
}


export async function fetchCandidateInvite(token) {
  const response = await fetch(`${API_BASE_URL}/api/candidate/invite/${encodeURIComponent(token)}`);
  const data = await response.json().catch(() => null);

  if (!response.ok || data?.success === false) {
    throw new Error(data?.detail || data?.message || "Invalid or expired interview link.");
  }

  return data;
}


export async function clearOldRecords(options = {}) {
  const query = options.clearApplications ? "?clear_applications=true" : "";
  const response = await fetch(`${API_BASE_URL}/api/dev/clear-old-records${query}`, {
    method: "POST",
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || data?.success === false) {
    throw new Error(data?.detail || data?.message || "Could not clear old records.");
  }

  return data;
}
