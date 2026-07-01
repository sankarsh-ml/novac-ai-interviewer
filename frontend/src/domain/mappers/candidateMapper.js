import { sortCandidatesByScore } from "../rules/candidateRules.js";

export function mapCandidateList(candidates) {
  return sortCandidatesByScore(Array.isArray(candidates) ? candidates : []);
}
