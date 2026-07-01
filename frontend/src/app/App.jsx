import AppRouter from "./router.jsx";
import AppProviders from "./providers.jsx";

function App() {
  return (
    <AppProviders>
      <AppRouter />
    </AppProviders>
  );
}

export default App;
