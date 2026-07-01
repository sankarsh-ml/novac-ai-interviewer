export function getLocalValue(key, fallback = null) {
  try {
    return window.localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

export function setLocalValue(key, value) {
  window.localStorage.setItem(key, value);
}

export function removeLocalValue(key) {
  window.localStorage.removeItem(key);
}
