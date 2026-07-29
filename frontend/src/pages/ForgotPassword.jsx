import { useState } from "react";
import { Link } from "react-router-dom";
import { forgotPassword } from "../api/auth";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await forgotPassword(email);
    } finally {
      // Always show the same message, whether or not the email exists --
      // matches the backend's response, which never reveals that either.
      setIsSubmitting(false);
      setSubmitted(true);
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
