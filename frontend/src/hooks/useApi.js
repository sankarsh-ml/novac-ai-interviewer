import { useAsync } from "./useAsync.js";

export function useApi(apiFunction) {
  return useAsync(apiFunction);
}
