import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { useNavigate } from "react-router-dom";
import {
  deleteSession,
  disable2FA,
  listSessions,
  logoutAll,
  setup2FA,
  verify2FASetup,
} from "../api/auth";
import { extractErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function AccountSecurity() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [error, setError] = useState(null);

  // 2FA setup flow state
  const [setupData, setSetupData] = useState(null); // {secret, otpauth_uri}
  const [setupCode, setSetupCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);

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

  async function handleStartSetup() {
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

  async function handleConfirmSetup(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await verify2FASetup(setupCode);
      setSetupData(null);
      setSetupCode("");
      setMessage("Two-factor authentication is now enabled on your account.");
      window.location.reload(); // simplest way to refresh user.totp_enabled from /auth/me
    } catch (err) {
      setError(extractErrorMessage(err, "Incorrect code. Check your authenticator app."));
    } finally {
      setBusy(false);
    }
  }

  async function handleDisable(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await disable2FA(disableCode);
      setDisableCode("");
      setMessage("Two-factor authentication has been disabled.");
      window.location.reload();
    } catch (err) {
      setError(extractErrorMessage(err, "Incorrect code."));
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
    await logout(); // also clears local tokens/state for the current tab
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
            <p>Two-factor authentication is <strong>enabled</strong> on your account.</p>
            <form onSubmit={handleDisable}>
              <div className="field">
                <label htmlFor="disable_code">Enter a code to disable it</label>
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
        ) : setupData ? (
          <div className="form-card" style={{ maxWidth: 420, margin: 0 }}>
            <p className="field-hint" style={{ marginTop: 0 }}>
              Scan this with your authenticator app (Google Authenticator, Authy, 1Password,
              etc.), then enter the 6-digit code it shows.
            </p>
            <div style={{ background: "#fff", padding: 16, display: "inline-block", marginBottom: 12 }}>
              <QRCodeSVG value={setupData.otpauth_uri} size={180} />
            </div>
            <p className="field-hint">
              Can't scan? Enter this key manually: <code>{setupData.secret}</code>
            </p>
            <form onSubmit={handleConfirmSetup}>
              <div className="field">
                <label htmlFor="setup_code">Code from your app</label>
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
          </div>
        ) : (
          <div>
            <p className="field-hint">
              Not enabled. Two-factor auth adds a code from your phone on top of your password
              at login.
            </p>
            <button className="btn btn-primary" onClick={handleStartSetup} disabled={busy}>
              Set up two-factor authentication
            </button>
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
