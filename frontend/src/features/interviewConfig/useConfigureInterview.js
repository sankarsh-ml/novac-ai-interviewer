import { configureQuestions, createInterviewLink, getConfigureData } from "../../services/interviewApi.js";
import {
  getDefaultDifficultySplit,
  validateDifficultySplit,
  validateQuestionSource,
  validateTotalQuestionCount,
} from "../../domain/rules/questionRules.js";
import { validateIdentityConfig } from "../../domain/rules/identityRules.js";

export function useConfigureInterview() {
  return {
    configureQuestions,
    createInterviewLink,
    getConfigureData,
    getDefaultDifficultySplit,
    validateDifficultySplit,
    validateIdentityConfig,
    validateQuestionSource,
    validateTotalQuestionCount,
  };
}
