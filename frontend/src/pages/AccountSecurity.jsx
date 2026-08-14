import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { useNavigate } from "react-router-dom";
import {
  deleteSession,
  disable2FA,
  disableEmailOtp,
  disableSmsOtp,
  listSessions,
  logoutAll,
  setup2FA,
  setupEmailOtp,
  setupSmsOtp,
  verify2FASetup,
  verifyEmailOtpSetup,
  verifySmsOtpSetup,
} from "../api/auth";
import { extractErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function AccountSecurity() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);

  // TOTP (authenticator app) setup flow state
  const [setupData, setSetupData] = useState(null); // {secret, otpauth_uri}
  const [setupCode, setSetupCode] = useState("");
  const [disableCode, setDisableCode] = useState("");

  // Email OTP setup flow state
  const [emailOtpPending, setEmailOtpPending] = useState(false);
  const [emailOtpCode, setEmailOtpCode] = useState("");

  // SMS OTP setup flow state
  const [phoneNumber, setPhoneNumber] = useState("");
  const [smsOtpPending, setSmsOtpPending] = useState(false);
  const [smsOtpCode, setSmsOtpCode] = useState("");

  // Which method to offer setting up when neither is enabled yet
  const [chosenMethod, setChosenMethod] = useState(null); // "totp" | "email_otp" | "sms_otp"

  async function loadSessions() {
    setIsLoadingSessions(true);
    try {
      const { data } = await listSessions();
      setSessions(data);
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't load your sessions."));
    } finally {
      setIsLoadingSessions(false);
    }
  }

  useEffect(() => {
    loadSessions();
  }, []);

  const canUse2FA = user.role === "authority" || user.role === "admin";
  const anyMethodEnabled = user.totp_enabled || user.email_otp_enabled || user.sms_otp_enabled;

  // --- TOTP handlers ---
  async function handleStartTotpSetup() {
    setError(null);
    setBusy(true);
    try {
      const { data } = await setup2FA();
      setSetupData(data);
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't start two-factor setup."));
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirmTotpSetup(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await verify2FASetup(setupCode);
      setMessage("Two-factor authentication is now enabled on your account.");
      window.location.reload();
    } catch (err) {
      setError(extractErrorMessage(err, "Incorrect code. Check your authenticator app."));
    } finally {
      setBusy(false);
    }
  }

  async function handleDisableTotp(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await disable2FA(disableCode);
      setMessage("Two-factor authentication has been disabled.");
      window.location.reload();
    } catch (err) {
      setError(extractErrorMessage(err, "Incorrect code."));
    } finally {
      setBusy(false);
    }
  }

  // --- Email OTP handlers ---
  async function handleStartEmailOtpSetup() {
    setError(null);
    setBusy(true);
    try {
      await setupEmailOtp();
      setEmailOtpPending(true);
      setMessage("A confirmation code has been sent to your email.");
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't start email-based two-factor setup."));
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirmEmailOtpSetup(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await verifyEmailOtpSetup(emailOtpCode);
      setMessage("Email-based two-factor authentication is now enabled.");
      window.location.reload();
    } catch (err) {
      setError(extractErrorMessage(err, "Incorrect or expired code."));
    } finally {
      setBusy(false);
    }
  }

  async function handleDisableEmailOtp() {
    setError(null);
    setBusy(true);
    try {
      await disableEmailOtp();
      setMessage("Email-based two-factor authentication has been disabled.");
      window.location.reload();
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't disable email-based two-factor authentication."));
    } finally {
      setBusy(false);
    }
  }

  // --- SMS OTP handlers ---
  async function handleStartSmsOtpSetup(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await setupSmsOtp(phoneNumber);
      setSmsOtpPending(true);
      setMessage("A confirmation code has been sent by SMS.");
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't start SMS-based two-factor setup."));
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirmSmsOtpSetup(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await verifySmsOtpSetup(smsOtpCode);
      setMessage("SMS-based two-factor authentication is now enabled.");
      window.location.reload();
    } catch (err) {
      setError(extractErrorMessage(err, "Incorrect or expired code."));
    } finally {
      setBusy(false);
    }
  }

  async function handleDisableSmsOtp() {
    setError(null);
    setBusy(true);
    try {
      await disableSmsOtp();
      setMessage("SMS-based two-factor authentication has been disabled.");
      window.location.reload();
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't disable SMS-based two-factor authentication."));
    } finally {
      setBusy(false);
    }
  }

  async function handleRevokeSession(sessionId) {
    setError(null);
    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't revoke that session."));
    }
  }

  async function handleLogoutAll() {
    await logoutAll();
    await logout();
    navigate("/");
  }

  return (
    <div className="container">
      <div className="page-header">
        <h2 style={{ margin: 0 }}>Account security</h2>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      <section style={{ marginBottom: 40 }}>
        <div className="section-heading">
          <h3 style={{ margin: 0 }}>Two-factor authentication</h3>
        </div>

        {!canUse2FA ? (
          <p className="field-hint">
            Two-factor authentication is available for authority and admin accounts.
          </p>
        ) : user.totp_enabled ? (
          <div className="form-card" style={{ maxWidth: 420, margin: 0 }}>
            <p>
              Two-factor authentication is <strong>enabled</strong> (authenticator app method).
            </p>
            <form onSubmit={handleDisableTotp}>
              <div className="field">
                <label htmlFor="disable_code">Enter a code from your app to disable it</label>
                <input
                  id="disable_code"
                  inputMode="numeric"
                  maxLength={6}
                  required
                  value={disableCode}
                  onChange={(e) => setDisableCode(e.target.value)}
                />
              </div>
              <button className="btn btn-danger" type="submit" disabled={busy}>
                Disable two-factor authentication
              </button>
            </form>
          </div>
        ) : user.email_otp_enabled ? (
          <div className="form-card" style={{ maxWidth: 420, margin: 0 }}>
            <p>
              Two-factor authentication is <strong>enabled</strong> (email code method). A code
              will be emailed to you at every login.
            </p>
            <button className="btn btn-danger" onClick={handleDisableEmailOtp} disabled={busy}>
              Disable two-factor authentication
            </button>
          </div>
        ) : user.sms_otp_enabled ? (
          <div className="form-card" style={{ maxWidth: 420, margin: 0 }}>
            <p>
              Two-factor authentication is <strong>enabled</strong> (SMS code method). A code
              will be texted to <strong>{user.phone_number}</strong> at every login.
            </p>
            <button className="btn btn-danger" onClick={handleDisableSmsOtp} disabled={busy}>
              Disable two-factor authentication
            </button>
          </div>
        ) : setupData ? (
          <div className="form-card" style={{ maxWidth: 420, margin: 0 }}>
            <p className="field-hint" style={{ marginTop: 0 }}>
              Open your authenticator app (Google Authenticator, Authy, 1Password, etc.), scan
              this QR code to add the account, then type the 6-digit code <strong>the app
              shows you</strong> (not shown on this page) into the box below.
            </p>
            <div style={{ background: "#fff", padding: 16, display: "inline-block", marginBottom: 12 }}>
              <QRCodeSVG value={setupData.otpauth_uri} size={180} />
            </div>
            <p className="field-hint">
              Can't scan? Enter this key manually: <code>{setupData.secret}</code>
            </p>
            <form onSubmit={handleConfirmTotpSetup}>
              <div className="field">
                <label htmlFor="setup_code">6-digit code from your authenticator app</label>
                <input
                  id="setup_code"
                  inputMode="numeric"
                  maxLength={6}
                  required
                  autoFocus
                  value={setupCode}
                  onChange={(e) => setSetupCode(e.target.value)}
                />
              </div>
              <button className="btn btn-primary" type="submit" disabled={busy}>
                Confirm and enable
              </button>
            </form>
            <button
              className="btn btn-secondary"
              style={{ marginTop: 8 }}
              onClick={() => { setSetupData(null); setChosenMethod(null); }}
            >
              Cancel
            </button>
          </div>
        ) : emailOtpPending ? (
          <div className="form-card" style={{ maxWidth: 420, margin: 0 }}>
            <p className="field-hint" style={{ marginTop: 0 }}>
              Check your email for a 6-digit confirmation code and enter it below.
            </p>
            <form onSubmit={handleConfirmEmailOtpSetup}>
              <div className="field">
                <label htmlFor="email_otp_code">Code from your email</label>
                <input
                  id="email_otp_code"
                  inputMode="numeric"
                  maxLength={6}
                  required
                  autoFocus
                  value={emailOtpCode}
                  onChange={(e) => setEmailOtpCode(e.target.value)}
                />
              </div>
              <button className="btn btn-primary" type="submit" disabled={busy}>
                Confirm and enable
              </button>
            </form>
            <p className="field-hint" style={{ marginTop: 10 }}>
              Didn't get it?{" "}
              <button
                type="button"
                onClick={handleStartEmailOtpSetup}
                disabled={busy}
                style={{ background: "none", border: "none", color: "var(--color-slate)", cursor: "pointer", textDecoration: "underline", padding: 0 }}
              >
                Resend code
              </button>
            </p>
            <button
              className="btn btn-secondary"
              style={{ marginTop: 8 }}
              onClick={() => { setEmailOtpPending(false); setChosenMethod(null); }}
            >
              Cancel
            </button>
          </div>
        ) : chosenMethod === "sms_otp" && smsOtpPending ? (
          <div className="form-card" style={{ maxWidth: 420, margin: 0 }}>
            <p className="field-hint" style={{ marginTop: 0 }}>
              Check your phone for a 6-digit confirmation code and enter it below.
            </p>
            <form onSubmit={handleConfirmSmsOtpSetup}>
              <div className="field">
                <label htmlFor="sms_otp_code">Code from the text message</label>
                <input
                  id="sms_otp_code"
                  inputMode="numeric"
                  maxLength={6}
                  required
                  autoFocus
                  value={smsOtpCode}
                  onChange={(e) => setSmsOtpCode(e.target.value)}
                />
              </div>
              <button className="btn btn-primary" type="submit" disabled={busy}>
                Confirm and enable
              </button>
            </form>
            <p className="field-hint" style={{ marginTop: 10 }}>
              Didn't get it?{" "}
              <button
                type="button"
                onClick={() => handleStartSmsOtpSetup({ preventDefault() {} })}
                disabled={busy}
                style={{ background: "none", border: "none", color: "var(--color-slate)", cursor: "pointer", textDecoration: "underline", padding: 0 }}
              >
                Resend code
              </button>
            </p>
            <button
              className="btn btn-secondary"
              style={{ marginTop: 8 }}
              onClick={() => { setSmsOtpPending(false); setChosenMethod(null); }}
            >
              Cancel
            </button>
          </div>
        ) : chosenMethod === "sms_otp" ? (
          <div className="form-card" style={{ maxWidth: 420, margin: 0 }}>
            <p className="field-hint" style={{ marginTop: 0 }}>
              Enter the phone number that should receive login codes, including the country
              code (e.g. +91XXXXXXXXXX).
            </p>
            <form onSubmit={handleStartSmsOtpSetup}>
              <div className="field">
                <label htmlFor="phone_number">Phone number</label>
                <input
                  id="phone_number"
                  type="tel"
                  required
                  autoFocus
                  placeholder="+91XXXXXXXXXX"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                />
              </div>
              <button className="btn btn-primary" type="submit" disabled={busy}>
                Send confirmation code
              </button>
            </form>
            <button
              className="btn btn-secondary"
              style={{ marginTop: 8 }}
              onClick={() => setChosenMethod(null)}
            >
              Cancel
            </button>
          </div>
        ) : (
          <div>
            <p className="field-hint">
              Not enabled. Two-factor auth adds a second step at login, on top of your password.
              Choose a method:
            </p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button className="btn btn-primary" onClick={handleStartTotpSetup} disabled={busy}>
                Use an authenticator app (scan a QR code)
              </button>
              <button className="btn btn-secondary" onClick={handleStartEmailOtpSetup} disabled={busy}>
                Email me a code at login instead
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => setChosenMethod("sms_otp")}
                disabled={busy}
              >
                Text me a code at login instead
              </button>
            </div>
          </div>
        )}
      </section>

      <section>
        <div className="section-heading">
          <h3 style={{ margin: 0 }}>Your sessions</h3>
        </div>
        <p className="field-hint">
          Every device you're currently logged in on. If you don't recognize one, revoke it.
        </p>

        {isLoadingSessions ? (
          <p className="spinner-text">Loading…</p>
        ) : sessions.length === 0 ? (
          <p className="field-hint">No active sessions found.</p>
        ) : (
          <div className="sighting-list" style={{ marginBottom: 16 }}>
            {sessions.map((s) => (
              <div key={s.session_id} className="sighting-item">
                <div className="sighting-item-header">
                  <span className="mono field-hint">{s.user_agent || "Unknown device"}</span>
                  <span className="sighting-item-meta">
                    {new Date(s.created_at).toLocaleString()}
                  </span>
                </div>
                <button
                  className="btn btn-secondary"
                  style={{ padding: "4px 10px", fontSize: "0.8rem" }}
                  onClick={() => handleRevokeSession(s.session_id)}
                >
                  Revoke this session
                </button>
              </div>
            ))}
          </div>
        )}

        <button className="btn btn-danger" onClick={handleLogoutAll}>
          Log out of all devices
        </button>
      </section>
    </div>
  );
}
