export function getDateFromIso(value) {
  const text = String(value || "");
  return text.includes("T") ? text.split("T")[0] : "";
}

export function getTimeFromIso(value) {
  const text = String(value || "");
  return text.includes("T") ? text.split("T")[1]?.slice(0, 5) || "" : "";
}
