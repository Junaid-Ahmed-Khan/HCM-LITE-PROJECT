
import Dashboard from "./components/Dashboard";
import { useEffect, useState } from "react";
import api from "./api/axios";
import "./App.css";

function App() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [user, setUser] = useState(null);

  useEffect(() => {
  const savedUser = sessionStorage.getItem("user");
  const accessToken = sessionStorage.getItem("access_token");

  if (savedUser && accessToken) {
    try {
      setUser(JSON.parse(savedUser));
    } catch {
      sessionStorage.removeItem("user");
      sessionStorage.removeItem("access_token");
      sessionStorage.removeItem("refresh_token");
    }
  }
}, []);

  const handleLogin = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await api.post("/auth/login", {
        email: email.trim().toLowerCase(),
        password,
      });

      const data = response.data;

      // Keep the session for this browser tab.
      sessionStorage.setItem("access_token", data.access_token);
      sessionStorage.setItem("refresh_token", data.refresh_token);
      sessionStorage.setItem("user", JSON.stringify(data.user));

      setUser(data.user);
      setPassword("");
    } catch (err) {
      if (err.response) {
        setError(
          typeof err.response.data?.detail === "string"
            ? err.response.data.detail
            : "Login failed. Please check your credentials."
        );
      } else {
        setError(
          "Cannot connect to the server. Check that the backend is running."
        );
      }
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
  const refreshToken = sessionStorage.getItem("refresh_token");

  try {
    if (refreshToken) {
      await api.post("/auth/logout", {
        refresh_token: refreshToken,
      });
    }
  } catch (error) {
    console.error("Server logout failed:", error);
  } finally {
    sessionStorage.removeItem("access_token");
    sessionStorage.removeItem("refresh_token");
    sessionStorage.removeItem("user");
    setUser(null);
    setEmail("");
    setPassword("");
    setError("");
  }
};

  if (user) {
  return <Dashboard user={user} onLogout={handleLogout} />;
}

  return (
    <main className="app-shell">
      <section className="login-card">
        <div className="brand-mark">H</div>
        <p className="eyebrow">HCM LITE</p>
        <h1>Welcome back</h1>
        <p className="subtitle">
          Sign in to manage your workplace.
        </p>

        <form onSubmit={handleLogin}>
          <div className="form-group">
            <label htmlFor="email">Email address</label>
            <input
              id="email"
              type="email"
              placeholder="you@company.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="username"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
          </div>

          {error && (
            <div className="error-message" role="alert">
              {error}
            </div>
          )}

          <button
            className="primary-button"
            type="submit"
            disabled={loading}
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="footer-note">
          Secure access for your organization
        </p>
      </section>
    </main>
  );
}

export default App;
