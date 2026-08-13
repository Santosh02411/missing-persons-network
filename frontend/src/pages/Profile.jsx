import { useState } from "react";
import { Link } from "react-router-dom";
import { updateAlertPreferences, updateJurisdiction } from "../api/auth";
import { extractErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import LocationPicker from "../components/LocationPicker";

const ROLE_LABELS = {
  reporter: "Citizen / public",
  authority: "Authority (police / NGO)",
  admin: "Admin",
};

const DASHBOARD_LINKS = {
  reporter: { to: "/dashboard/citizen", label: "Go to my dashboard" },
  authority: { to: "/dashboard/authority", label: "Go to authority dashboard" },
  admin: { to: "/dashboard/admin", label: "Go to admin dashboard" },
};

export default function Profile() {
  const { user, refreshUser } = useAuth();
  const dashboard = DASHBOARD_LINKS[user.role];

  const [isEditingStation, setIsEditingStation] = useState(false);
  const [stationLocation, setStationLocation] = useState(user.jurisdiction_location || null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const [isEditingAlerts, setIsEditingAlerts] = useState(false);
  const [alertLocation, setAlertLocation] = useState(user.alert_location || null);
  const [alertRadius, setAlertRadius] = useState(user.alert_radius_km || 20);
  const [isSavingAlerts, setIsSavingAlerts] = useState(false);
  const [alertError, setAlertError] = useState(null);

  async function handleSaveStation() {
    if (!stationLocation) return;
    setSaveError(null);
    setIsSaving(true);
    try {
      await updateJurisdiction(stationLocation);
      if (refreshUser) await refreshUser();
      setIsEditingStation(false);
    } catch (err) {
      setSaveError(extractErrorMessage(err, "Couldn't save your station location."));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleSaveAlertPreferences(enabled) {
    if (enabled && !alertLocation) return;
    setAlertError(null);
    setIsSavingAlerts(true);
    try {
      await updateAlertPreferences({
        enabled,
        location: alertLocation,
        radius_km: alertRadius ? Number(alertRadius) : null,
      });
      if (refreshUser) await refreshUser();
      setIsEditingAlerts(false);
    } catch (err) {
      setAlertError(extractErrorMessage(err, "Couldn't save your alert preferences."));
    } finally {
      setIsSavingAlerts(false);
    }
  }

  const twoFactorLabel = user.totp_enabled
    ? "Enabled (authenticator app)"
    : user.email_otp_enabled
      ? "Enabled (email code)"
      : user.sms_otp_enabled
        ? "Enabled (SMS code)"
        : "Not enabled";

  return (
    <div className="container" style={{ maxWidth: 720 }}>
      <div className="page-header">
        <h2 style={{ margin: 0 }}>My profile</h2>
        <div className="row">
          {dashboard && (
            <Link to={dashboard.to} className="btn btn-primary">
              {dashboard.label}
            </Link>
          )}
          <Link to="/account/security" className="btn btn-secondary">
            Security settings
          </Link>
        </div>
      </div>

      <div className="form-card" style={{ maxWidth: "none" }}>
        {/* ---------- Account ---------- */}
        <div className="detail-section">
          <div className="detail-section-title">Account</div>
          <div className="detail-list">
            <div className="detail-row">
              <div className="detail-row-label">Name</div>
              <div className="detail-row-value">{user.full_name}</div>
            </div>
            <div className="detail-row">
              <div className="detail-row-label">Email</div>
              <div className="detail-row-value row">
                {user.email}
                {user.email_verified ? (
                  <span className="status-badge status-verified">Verified</span>
                ) : (
                  <span className="status-badge status-pending">Not verified</span>
                )}
              </div>
            </div>
            <div className="detail-row">
              <div className="detail-row-label">Role</div>
              <div className="detail-row-value">{ROLE_LABELS[user.role] || user.role}</div>
            </div>
            <div className="detail-row">
              <div className="detail-row-label">Two-factor authentication</div>
              <div className="detail-row-value">{twoFactorLabel}</div>
            </div>
          </div>
        </div>

        {/* ---------- Authority details ---------- */}
        {user.role === "authority" && (
          <div className="detail-section">
            <div className="detail-section-title">Authority details</div>
            <div className="detail-list">
              <div className="detail-row">
                <div className="detail-row-label">Organization</div>
                <div className="detail-row-value">{user.org_name || "—"}</div>
              </div>
              <div className="detail-row">
                <div className="detail-row-label">Account status</div>
                <div className="detail-row-value">
                  {user.is_verified ? (
                    <span className="status-badge status-verified">Approved</span>
                  ) : (
                    <span className="status-badge status-pending">Awaiting admin approval</span>
                  )}
                </div>
              </div>
              <div className="detail-row">
                <div className="detail-row-label">Station / office location</div>
                <div className="detail-row-value">
                  {!isEditingStation ? (
                    <div className="row-between">
                      {user.jurisdiction_location ? (
                        <span>
                          Set — {user.jurisdiction_location.lat.toFixed(4)}, {user.jurisdiction_location.lng.toFixed(4)}
                        </span>
                      ) : (
                        <span className="field-hint" style={{ marginTop: 0 }}>
                          Not set — cases won't auto-route to you until this is set.
                        </span>
                      )}
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => setIsEditingStation(true)}
                      >
                        {user.jurisdiction_location ? "Update" : "Set location"}
                      </button>
                    </div>
                  ) : null}
                </div>
                {isEditingStation && (
                  <div className="detail-row-edit stack-sm">
                    {saveError && <div className="alert alert-error" style={{ marginBottom: 0 }}>{saveError}</div>}
                    <LocationPicker value={stationLocation} onChange={setStationLocation} />
                    <div className="row">
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={!stationLocation || isSaving}
                        onClick={handleSaveStation}
                      >
                        {isSaving ? "Saving…" : "Save location"}
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => setIsEditingStation(false)}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ---------- Alerts ---------- */}
        <div className="detail-section">
          <div className="detail-section-title">Geofenced alerts</div>
          <div className="detail-list">
            <div className="detail-row">
              <div className="detail-row-label">Alerts</div>
              <div className="detail-row-value">
                {!isEditingAlerts ? (
                  <div className="row-between">
                    {user.alerts_enabled ? (
                      <span className="row">
                        <span className="status-badge status-verified">On</span>
                        <span className="field-hint" style={{ margin: 0 }}>
                          within {user.alert_radius_km}km of your chosen location
                        </span>
                      </span>
                    ) : (
                      <span className="field-hint" style={{ margin: 0 }}>
                        Off — get emailed when an authority pushes an alert for a new case near a
                        place you choose.
                      </span>
                    )}
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => setIsEditingAlerts(true)}
                    >
                      {user.alerts_enabled ? "Update" : "Turn on"}
                    </button>
                  </div>
                ) : null}
              </div>
              {isEditingAlerts && (
                <div className="detail-row-edit stack-sm">
                  {alertError && <div className="alert alert-error" style={{ marginBottom: 0 }}>{alertError}</div>}
                  <LocationPicker value={alertLocation} onChange={setAlertLocation} />
                  <div className="field" style={{ marginBottom: 0, maxWidth: 160 }}>
                    <label htmlFor="alert-radius">Radius (km)</label>
                    <input
                      id="alert-radius"
                      type="number"
                      min="1"
                      max="500"
                      value={alertRadius}
                      onChange={(e) => setAlertRadius(e.target.value)}
                    />
                  </div>
                  <div className="row">
                    <button
                      type="button"
                      className="btn btn-primary"
                      disabled={!alertLocation || isSavingAlerts}
                      onClick={() => handleSaveAlertPreferences(true)}
                    >
                      {isSavingAlerts ? "Saving…" : "Save and turn on"}
                    </button>
                    {user.alerts_enabled && (
                      <button
                        type="button"
                        className="btn btn-danger"
                        disabled={isSavingAlerts}
                        onClick={() => handleSaveAlertPreferences(false)}
                      >
                        Turn off
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setIsEditingAlerts(false)}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
