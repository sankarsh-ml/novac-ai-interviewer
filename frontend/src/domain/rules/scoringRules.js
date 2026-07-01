export function getScoreValue(value) {
  if (value === null || value === undefined || value === "" || typeof value === "boolean") {
    return null;
  }

  if (typeof value === "number") {
    return Number.isFinite(value) ? Math.max(0, Math.min(10, value)) : null;
  }

  const match = String(value).match(/-?\d+(?:\.\d+)?/);

  if (!match) {
    return null;
  }

  const number = Number(match[0]);
  return Number.isFinite(number) ? Math.max(0, Math.min(10, number)) : null;
}

export function formatScore(value) {
  const score = getScoreValue(value);
  return score === null ? "Not graded" : score.toFixed(1);
}
