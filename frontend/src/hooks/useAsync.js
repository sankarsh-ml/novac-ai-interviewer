import { useCallback, useState } from "react";

export function useAsync(asyncFunction) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const execute = useCallback(async (...args) => {
    setLoading(true);
    setError("");

    try {
      return await asyncFunction(...args);
    } catch (caughtError) {
      setError(caughtError.message || "Request failed.");
      throw caughtError;
    } finally {
      setLoading(false);
    }
  }, [asyncFunction]);

  return { execute, loading, error, setError };
}
