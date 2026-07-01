export function getCandidateDecisionBadge(candidate) {
  if (isHrDecision(candidate, "selected")) {
    return { label: "Selected", className: "status-pass" };
  }

  if (isHrDecision(candidate, "rejected")) {
    return { label: "Rejected", className: "status-fail" };
  }

  return { label: "Pending", className: "status-processing" };
}

export function getAtsStatusBadge(status) {
  const normalized = String(status || "").toLowerCase();

  if (normalized === "passed") {
    return { label: "Passed", className: "status-pass" };
  }

  if (normalized === "failed") {
    return { label: "Failed", className: "status-fail" };
  }

  return { label: formatStatus(status || "processing"), className: "status-processing" };
}

export function canQuickSelectCandidate(candidate) {
  return !isHrDecision(candidate, "selected") && !isHrDecision(candidate, "rejected");
}

export function calculateCandidateStats(candidates) {
  const list = Array.isArray(candidates) ? candidates : [];
  return {
    total: list.length,
    selected: list.filter((candidate) => isHrDecision(candidate, "selected")).length,
    rejected: list.filter((candidate) => isHrDecision(candidate, "rejected")).length,
  };
}

export function sortCandidatesByScore(candidates) {
  return [...(candidates || [])].sort((a, b) => getRankScore(b) - getRankScore(a));
}

export function getRankScore(candidate) {
  const value = candidate?.ats_score ?? candidate?.ats_result?.ats_score ?? 0;
  const score = Number(value);
  return Number.isFinite(score) ? score : 0;
}

export function isHrDecision(candidate, decision) {
  return String(candidate?.hr_decision || "").toLowerCase().trim() === decision;
}

export function formatStatus(value) {
  return String(value || "Not Started")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
