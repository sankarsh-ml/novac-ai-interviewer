import { useState } from "react";
import { loginAdmin } from "../../services/adminApi.js";
import "../../styles/AdminLoginPage.css";

function AdminLoginPage({ onLoginSuccess, onBack }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleLogin = async (e) => {
    e.preventDefault();

    if (!username || !password) {
      alert("Please enter both username and password.");
      return;
    }

    try {
      const data = await loginAdmin(username, password);

      if (data.success) {
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
