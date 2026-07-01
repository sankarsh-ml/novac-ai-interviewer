import AppRouter from "./app/router.jsx";
import AppProviders from "./app/providers.jsx";

function App() {
  return (
    <AppProviders>
      <AppRouter />
    </AppProviders>
  );
}

export default App;
