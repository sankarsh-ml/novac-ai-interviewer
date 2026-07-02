import { useState } from "react";
import { loginAdmin } from "@application/useCases/adminUseCases.js";
import { useDependencies } from "@presentation/hooks/useDependencies.js";
import { ADMIN_TOKEN_KEY } from "@infrastructure/api/apiClient.js";
import { removeLocalValue, setLocalValue } from "@infrastructure/storage/localStorageClient.js";
import "@presentation/styles/AdminLoginPage.css";

function AdminLoginPage({ onLoginSuccess, onBack }) {
  const { adminRepository } = useDependencies();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleLogin = async (e) => {
    e.preventDefault();

    if (!username || !password) {
      alert("Please enter both username and password.");
      return;
    }

    try {
      const data = await loginAdmin(adminRepository, username, password);

      if (data.success) {
        if (data.access_token) {
          setLocalValue(ADMIN_TOKEN_KEY, data.access_token);
          removeLocalValue("novac_admin_access_token");
        }

        onLoginSuccess();
      } else {
        alert(data.message);
      }
    } catch (error) {
      console.error(error);
      alert(error.message || "Unable to connect to the server.");
    }
  };

  return (
    <main className="login-page">
      <div className="login-card">
        <h1>Admin Login</h1>
        <p>Please login to continue</p>

        <form onSubmit={handleLogin}>
          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />

          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <button type="submit">
            Login
          </button>
        </form>

        <button className="back-btn" onClick={onBack}>
          Back
        </button>
      </div>
    </main>
  );
}

export default AdminLoginPage;
