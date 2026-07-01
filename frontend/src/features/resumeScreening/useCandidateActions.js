import {
  deleteAllRecords,
  deleteCandidate,
  quickSelectCandidates,
  updateCandidateDecision,
} from "../../services/candidateApi.js";

export function useCandidateActions() {
  return {
    deleteAllRecords,
    deleteCandidate,
    quickSelectCandidates,
    updateCandidateDecision,
  };
}
