import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { resetPassword } from "../api/auth";
import { extractErrorMessage } from "../api/client";

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const navigate = useNavigate();

  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await resetPassword(token, newPassword);
      setSuccess(true);
      setTimeout(() => navigate("/login"), 2000);
    } catch (err) {
      setError(extractErrorMessage(err, "That reset link is invalid or has expired."));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!token) {
    return (
      <div className="container">
        <div className="form-card">
          <div className="alert alert-error">
            This link is missing a reset token. Request a new one from{" "}
            <Link to="/forgot-password">the forgot-password page</Link>.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="form-card">
        <h2>Choose a new password</h2>
        {success ? (
          <div className="alert alert-success">
            Password updated. Redirecting you to log in…
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            {error && <div className="alert alert-error">{error}</div>}
            <div className="field">
              <label htmlFor="new_password">New password</label>
              <input
                id="new_password"
                type="password"
                minLength={8}
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
              <p className="field-hint">At least 8 characters.</p>
            </div>
            <button className="btn btn-primary btn-block" type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Updating…" : "Update password"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
