export function isPdfFile(file) {
  return Boolean(file?.name?.toLowerCase().endsWith(".pdf"));
}

export function hasAllowedExtension(file, extensions) {
  const fileName = String(file?.name || "").toLowerCase();
  return extensions.some((extension) => fileName.endsWith(extension));
}
