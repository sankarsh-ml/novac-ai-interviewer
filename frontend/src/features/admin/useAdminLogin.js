import { useState } from "react";

import { loginAdmin } from "../../services/adminApi.js";

export function useAdminLogin(onLoginSuccess) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const login = async (username, password) => {
    if (!username || !password) {
      throw new Error("Please enter both username and password.");
    }

    setLoading(true);
    setError("");

    try {
      const data = await loginAdmin(username, password);
      onLoginSuccess?.(data);
      return data;
    } catch (caughtError) {
      setError(caughtError.message || "Login failed.");
      throw caughtError;
    } finally {
      setLoading(false);
    }
  };

  return { login, loading, error };
}
