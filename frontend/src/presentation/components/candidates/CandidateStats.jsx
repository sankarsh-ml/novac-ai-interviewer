import { calculateCandidateStats } from "@domain/rules/candidateRules.js";

function CandidateStats({ candidates }) {
  const stats = calculateCandidateStats(candidates);

  return (
    <div className="job-summary">
      <div className="summary-card">
        <span>Total Applications</span>
        <strong>{stats.total}</strong>
      </div>
      <div className="summary-card">
        <span>Selected</span>
        <strong>{stats.selected}</strong>
      </div>
      <div className="summary-card">
        <span>Rejected</span>
        <strong>{stats.rejected}</strong>
      </div>
    </div>
  );
}

export default CandidateStats;
