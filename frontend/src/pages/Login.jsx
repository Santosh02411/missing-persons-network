import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const from = location.state?.from?.pathname || "/";

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(form);
      navigate(from, { replace: true });
    } catch (err) {
      setError(extractErrorMessage(err, "Incorrect email or password."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="container">
      <div className="form-card">
        <h2>Log in</h2>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              required
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </div>
          <button className="btn btn-primary btn-block" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Logging in…" : "Log in"}
          </button>
        </form>
        <p className="field-hint" style={{ marginTop: "16px", textAlign: "center" }}>
          Don't have an account? <Link to="/register">Register</Link>
        </p>
      </div>
    </div>
  );
}
