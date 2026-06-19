import { useState } from "react";

import HomePage from "./pages/HomePage.jsx";
import StudentUploadPage from "./pages/StudentUploadPage.jsx";


function App() {
  const [currentPage, setCurrentPage] = useState("home");

  if (currentPage === "student") {
    return <StudentUploadPage onBack={() => setCurrentPage("home")} />;
  }

  return <HomePage onOpenStudent={() => setCurrentPage("student")} />;
}


export default App;
