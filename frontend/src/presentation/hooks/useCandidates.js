import { useCallback, useEffect, useState } from "react";

import { fetchCandidates } from "@application/useCases/candidateUseCases.js";
import { mapCandidateList } from "@application/mappers/candidateMapper.js";
import { useDependencies } from "./useDependencies.js";

export function useCandidates(jobId) {
  const { candidateRepository } = useDependencies();
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refreshCandidates = useCallback(async () => {
    if (!jobId) {
      setApplications([]);
      return [];
    }

    setLoading(true);
    setError("");

    try {
      const data = await fetchCandidates(candidateRepository, jobId);
      const sorted = mapCandidateList(data.applications || []);
      setApplications(sorted);
      return sorted;
    } catch (caughtError) {
      setError(caughtError.message || "Failed to fetch candidates.");
      return [];
    } finally {
      setLoading(false);
    }
  }, [candidateRepository, jobId]);

  useEffect(() => {
    refreshCandidates();
  }, [refreshCandidates]);

  return { applications, setApplications, loading, error, refreshCandidates };
}
