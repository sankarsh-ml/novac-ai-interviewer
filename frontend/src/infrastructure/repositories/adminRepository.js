import { apiRequest } from "../api/apiClient.js";
import { endpoints } from "../config/endpoints.js";

export function loginAdmin(username, password) {
  return apiRequest(endpoints.adminLogin, {
    auth: "none",
    method: "POST",
    body: { username, password },
  });
}
