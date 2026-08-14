import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import { resendMfaCode } from "../api/auth";
import { useAuth } from "../context/AuthContext";
import PasswordField from "../components/PasswordField";
import AuthLayout from "../components/AuthLayout";

export default function Login() {
  const { login, completeMfaLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Two-factor step: once the password check succeeds for a 2FA-enabled
  // account, we hold onto the mfa_token and show a second form for the code.
  const [mfaToken, setMfaToken] = useState(null);
  const [mfaMethod, setMfaMethod] = useState(null); // "totp" | "email_otp"
  const [code, setCode] = useState("");
  const [resendState, setResendState] = useState("idle"); // "idle" | "sending" | "sent"
  const [resendCooldown, setResendCooldown] = useState(0);

  const from = location.state?.from?.pathname || "/";

  async function handleResend() {
    setError(null);
    setResendState("sending");
    try {
      await resendMfaCode(mfaToken);
      setResendState("sent");
      setResendCooldown(30);
      const timer = setInterval(() => {
        setResendCooldown((prev) => {
          if (prev <= 1) {
            clearInterval(timer);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } catch (err) {
      setResendState("idle");
      setError(extractErrorMessage(err, "Couldn't resend the code. Please wait a moment and try again."));
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const result = await login(form);
      if (result.mfaRequired) {
        setMfaToken(result.mfaToken);
        setMfaMethod(result.mfaMethod);
      } else {
        navigate(from, { replace: true });
      }
    } catch (err) {
      setError(extractErrorMessage(err, "Incorrect email or password."));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleMfaSubmit(e) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await completeMfaLogin(mfaToken, code);
      navigate(from, { replace: true });
    } catch (err) {
      setError(extractErrorMessage(err, "Incorrect code. Please try again."));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (mfaToken) {
    return (
      <AuthLayout
        eyebrow="National Missing Persons Registry"
        title="One more step to keep your account safe."
        body="Two-factor authentication protects the cases and sightings you're trusted with."
      >
        <h2>Two-factor verification</h2>
        <p className="field-hint" style={{ marginTop: -8, marginBottom: 20 }}>
          {mfaMethod === "email_otp"
            ? "We just emailed a 6-digit code to your registered address. Enter it below."
            : mfaMethod === "sms_otp"
            ? "We just texted a 6-digit code to your registered phone number. Enter it below."
            : "Enter the 6-digit code from your authenticator app."}
        </p>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={handleMfaSubmit}>
          <div className="field">
            <label htmlFor="code">Authentication code</label>
            <input
              id="code"
              inputMode="numeric"
              pattern="[0-9]{6}"
              maxLength={6}
              required
              autoFocus
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </div>
          <button className="btn btn-primary btn-block" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Verifying…" : "Verify and log in"}
          </button>
        </form>
        {(mfaMethod === "email_otp" || mfaMethod === "sms_otp") && (
          <p className="field-hint" style={{ marginTop: "16px", textAlign: "center" }}>
            Didn't get a code?{" "}
            <button
              type="button"
              onClick={handleResend}
              disabled={resendState === "sending" || resendCooldown > 0}
              style={{
                background: "none",
                border: "none",
                color: "var(--color-slate)",
                cursor: resendCooldown > 0 ? "default" : "pointer",
                textDecoration: resendCooldown > 0 ? "none" : "underline",
                padding: 0,
              }}
            >
              {resendState === "sending"
                ? "Sending…"
                : resendCooldown > 0
                ? `Resend code (${resendCooldown}s)`
                : "Resend code"}
            </button>
          </p>
        )}
        <p className="field-hint" style={{ marginTop: "8px", textAlign: "center" }}>
          <button
            type="button"
            onClick={() => { setMfaToken(null); setMfaMethod(null); }}
            style={{ background: "none", border: "none", color: "var(--color-slate)", cursor: "pointer", textDecoration: "underline" }}
          >
            Back to login
          </button>
        </p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      eyebrow="National Missing Persons Registry"
      title="A light kept on for every family still searching."
      body="Log in to file a case, review sightings, or manage the cases assigned to your station."
    >
      <h2>Log in</h2>
      {error && <div className="alert alert-error">{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </div>
        <PasswordField
          id="password"
          label="Password"
          required
          autoComplete="current-password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        />
        <button className="btn btn-primary btn-block" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Logging in…" : "Log in"}
        </button>
      </form>
      <p className="field-hint" style={{ marginTop: "12px", textAlign: "center" }}>
        <Link to="/forgot-password">Forgot your password?</Link>
      </p>
      <p className="field-hint" style={{ marginTop: "8px", textAlign: "center" }}>
        Don't have an account? <Link to="/register">Register</Link>
      </p>
    </AuthLayout>
  );
}
