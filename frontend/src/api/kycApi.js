const API_BASE_URL = "http://127.0.0.1:8000";

export async function uploadAadhaar(applicationId, aadhaarFile) {
  const cleanApplicationId = String(applicationId || "").trim();

  console.log("[KYC] applicationId:", cleanApplicationId);
  console.log("[KYC] aadhaarFile:", aadhaarFile);

  if (!cleanApplicationId) {
    throw new Error("Application ID missing. Please upload resume again.");
  }

  if (!aadhaarFile) {
    throw new Error("Please select an Aadhaar file.");
  }

  const formData = new FormData();
  formData.append("aadhaar_file", aadhaarFile);

  const url = `${API_BASE_URL}/api/kyc/aadhaar/upload/${encodeURIComponent(
    cleanApplicationId
  )}`;

  console.log("[KYC] POST:", url);

  let response;

  try {
    response = await fetch(url, {
      method: "POST",
      body: formData,
    });
  } catch (error) {
    console.error("[KYC] Network/CORS/server-crash error:", error);

    throw new Error(
      "KYC request could not reach FastAPI or the backend crashed during processing. Check the FastAPI terminal for traceback."
    );
  }

  let data = null;

  try {
    data = await response.json();
  } catch (error) {
    console.error("[KYC] Backend returned non-JSON response:", error);
    throw new Error(`Backend returned invalid response. HTTP ${response.status}`);
  }

  console.log("[KYC] HTTP status:", response.status);
  console.log("[KYC] response:", data);

  if (!response.ok || data?.success === false) {
    throw new Error(
      data?.message ||
        data?.detail ||
        `Aadhaar verification failed. HTTP ${response.status}`
    );
  }

  return data;
}