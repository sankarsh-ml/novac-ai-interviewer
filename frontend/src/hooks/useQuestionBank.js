import { useCallback, useEffect, useState } from "react";

import { getQuestionBank } from "../services/questionBankApi.js";

export function useQuestionBank(jobId) {
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(false);

  const refreshQuestionBank = useCallback(async () => {
    if (!jobId) {
      setQuestions([]);
      return [];
    }

    setLoading(true);

    try {
      const data = await getQuestionBank(jobId);
      const loadedQuestions = Array.isArray(data.questions) ? data.questions : [];
      setQuestions(loadedQuestions);
      return loadedQuestions;
    } catch (error) {
      console.error("Failed to fetch question bank:", error);
      setQuestions([]);
      return [];
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    refreshQuestionBank();
  }, [refreshQuestionBank]);

  return { questions, setQuestions, loading, refreshQuestionBank };
}
