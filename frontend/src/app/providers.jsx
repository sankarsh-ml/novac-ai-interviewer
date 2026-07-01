import { repositories } from "@infrastructure/repositories/index.js";
import { DependenciesContext } from "@presentation/hooks/useDependencies.js";

function AppProviders({ children }) {
  return (
    <DependenciesContext.Provider value={repositories}>
      {children}
    </DependenciesContext.Provider>
  );
}

export default AppProviders;
