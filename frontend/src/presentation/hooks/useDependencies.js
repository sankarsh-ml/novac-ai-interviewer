import { createContext, useContext } from "react";

export const DependenciesContext = createContext(null);

export function useDependencies() {
  const dependencies = useContext(DependenciesContext);

  if (!dependencies) {
    throw new Error("Application dependencies were not provided.");
  }

  return dependencies;
}
