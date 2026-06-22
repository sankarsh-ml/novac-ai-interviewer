const API_BASE_URL = "http://127.0.0.1:8000";


export async function uploadResume(file) {
  const formData = new FormData();
  formData.append("resume_file", file);

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
