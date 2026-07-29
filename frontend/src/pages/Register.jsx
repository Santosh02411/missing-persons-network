import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    email: "",
    password: "",
    full_name: "",
    role: "reporter",
    org_name: "",
  });
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function updateField(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await register(form);
      navigate("/", { replace: true });
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't create your account."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="container">
      <div className="form-card">
        <h2>Create an account</h2>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="full_name">Full name</label>
            <input
              id="full_name"
              required
              value={form.full_name}
              onChange={(e) => updateField("full_name", e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              required
              value={form.email}
              onChange={(e) => updateField("email", e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              minLength={8}
              required
              value={form.password}
              onChange={(e) => updateField("password", e.target.value)}
            />
            <p className="field-hint">At least 8 characters.</p>
          </div>
          <div className="field">
            <label htmlFor="role">Account type</label>
            <select id="role" value={form.role} onChange={(e) => updateField("role", e.target.value)}>
              <option value="reporter">Public reporter</option>
              <option value="authority">Police / NGO (authority)</option>
            </select>
            {form.role === "authority" && (
              <p className="field-hint">
                Authority accounts need admin approval before they can review sightings or
                update case status.
              </p>
            )}
          </div>
          {form.role === "authority" && (
            <div className="field">
              <label htmlFor="org_name">Organization name</label>
              <input
                id="org_name"
                required
                placeholder="e.g. Belagavi City Police"
                value={form.org_name}
                onChange={(e) => updateField("org_name", e.target.value)}
              />
            </div>
          )}
          <button className="btn btn-primary btn-block" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Creating account…" : "Create account"}
          </button>
        </form>
        <p className="field-hint" style={{ marginTop: "16px", textAlign: "center" }}>
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  );
}
