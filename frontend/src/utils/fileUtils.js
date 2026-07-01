export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "download";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function openBlob(blob, targetWindow) {
  const url = URL.createObjectURL(blob);
  targetWindow.location.href = url;
  window.setTimeout(() => URL.revokeObjectURL(url), 60 * 1000);
}

export function downloadTextFile(content, filename, type) {
  downloadBlob(new Blob([content], { type }), filename);
}
