export function getErrorMessage(error, fallback) {
  return error?.message || fallback || "Something went wrong.";
}
