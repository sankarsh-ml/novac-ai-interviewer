import { apiRequest } from "../infrastructure/api/apiClient.js";
import { endpoints } from "../infrastructure/api/endpoints.js";

export function loginAdmin(username, password) {
  return apiRequest(endpoints.adminLogin, {
    method: "POST",
    body: { username, password },
  });
}
