const API_URL = "http://127.0.0.1:8000/api/resume/extract-text";


export async function uploadResume(file) {
  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch(API_URL, {
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
    throw error;
  }
}
