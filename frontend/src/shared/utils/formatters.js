export function formatStatus(value) {
  return String(value || "Not Available")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function safeFilename(value) {
  return String(value || "candidate")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "") || "candidate";
}
