import { useState } from "react";
import { Link } from "react-router-dom";
import { forgotPassword } from "../api/auth";
import { extractErrorMessage } from "../api/client";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      await forgotPassword(email);
      // The backend intentionally returns the same generic response whether
      // or not this email is registered (prevents account enumeration) --
      // that's the ONLY thing that gets this generic "check your email"
      // message. A genuine request failure (network error, CORS, a 500) is
      // a different thing and should actually be shown, not silently
      // treated as if it worked -- this used to always show "success" here
      // even when the request itself never reached the backend at all.
      setSubmitted(true);
    } catch (err) {
      setError(extractErrorMessage(err, "Something went wrong sending that. Please try again."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="container">
      <div className="form-card">
        <h2>Forgot your password?</h2>
        {submitted ? (
          <div className="alert alert-success">
            If that email is registered, a password reset link has been sent. Check the
            address you entered.
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            {error && <div className="alert alert-error">{error}</div>}
            <p className="field-hint" style={{ marginTop: -8, marginBottom: 16 }}>
              Enter your email and we'll send you a link to reset your password.
            </p>
            <div className="field">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <button className="btn btn-primary btn-block" type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Sending…" : "Send reset link"}
            </button>
          </form>
        )}
        <p className="field-hint" style={{ marginTop: "16px", textAlign: "center" }}>
          <Link to="/login">Back to log in</Link>
        </p>
      </div>
    </div>
  );
}
