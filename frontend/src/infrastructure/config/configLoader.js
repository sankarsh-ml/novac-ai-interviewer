import config from "./config.json";

export function getAppConfig() {
  return config;
}

export function getApiBaseUrl() {
  return import.meta.env.VITE_API_BASE_URL || config.api.baseUrl;
}

export function getFeatureConfig() {
  return config.features;
}
