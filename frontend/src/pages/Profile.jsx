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

  return (
    <div className="container">
      <div className="page-header">
        <h2 style={{ margin: 0 }}>My profile</h2>
      </div>

      <div className="form-card" style={{ maxWidth: 480 }}>
        <div className="case-detail-label">Name</div>
        <div>{user.full_name}</div>

        <div className="case-detail-label">Email</div>
        <div>
          {user.email}{" "}
          {user.email_verified ? (
            <span className="status-badge status-verified">Verified</span>
          ) : (
            <span className="status-badge status-pending">Not verified</span>
          )}
        </div>

        <div className="case-detail-label">Role</div>
        <div>{ROLE_LABELS[user.role] || user.role}</div>

        {user.role === "authority" && (
          <>
            <div className="case-detail-label">Organization</div>
            <div>{user.org_name || "—"}</div>

            <div className="case-detail-label">Account status</div>
            <div>
              {user.is_verified ? (
                <span className="status-badge status-verified">Approved</span>
              ) : (
                <span className="status-badge status-pending">Awaiting admin approval</span>
              )}
            </div>

            <div className="case-detail-label">Station / office location</div>
            {!isEditingStation ? (
              <div>
                {user.jurisdiction_location ? (
                  <>
                    Set — {user.jurisdiction_location.lat.toFixed(4)},{" "}
                    {user.jurisdiction_location.lng.toFixed(4)}{" "}
                  </>
                ) : (
                  <span className="field-hint">
                    Not set — cases won't auto-route to you until this is set.{" "}
                  </span>
                )}
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ padding: "4px 10px", fontSize: "0.82rem" }}
                  onClick={() => setIsEditingStation(true)}
                >
                  {user.jurisdiction_location ? "Update" : "Set location"}
                </button>
              </div>
            ) : (
              <div style={{ marginTop: 8 }}>
                {saveError && <div className="alert alert-error">{saveError}</div>}
                <LocationPicker value={stationLocation} onChange={setStationLocation} />
                <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
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
          </>
        )}

        <div className="case-detail-label">Two-factor authentication</div>
        <div>
          {user.totp_enabled
            ? "Enabled (authenticator app)"
            : user.email_otp_enabled
              ? "Enabled (email code)"
              : user.sms_otp_enabled
                ? "Enabled (SMS code)"
                : "Not enabled"}
        </div>

        <div className="case-detail-label">Geofenced alerts</div>
        {!isEditingAlerts ? (
          <div>
            {user.alerts_enabled ? (
              <>
                <span className="status-badge status-verified">On</span>{" "}
                <span className="field-hint">
                  within {user.alert_radius_km}km of your chosen location
                </span>
              </>
            ) : (
              <span className="field-hint">
                Off — get emailed when an authority pushes an alert for a new case near a place
                you choose.
              </span>
            )}{" "}
            <button
              type="button"
              className="btn btn-secondary"
              style={{ padding: "4px 10px", fontSize: "0.82rem", marginTop: 4 }}
              onClick={() => setIsEditingAlerts(true)}
            >
              {user.alerts_enabled ? "Update" : "Turn on"}
            </button>
          </div>
        ) : (
          <div style={{ marginTop: 8 }}>
            {alertError && <div className="alert alert-error">{alertError}</div>}
            <LocationPicker value={alertLocation} onChange={setAlertLocation} />
            <div className="field" style={{ marginTop: 8, maxWidth: 160 }}>
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
            <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
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
              <button type="button" className="btn btn-secondary" onClick={() => setIsEditingAlerts(false)}>
                Cancel
              </button>
            </div>
          </div>
        )}

        <div style={{ marginTop: 20, display: "flex", gap: 8, flexWrap: "wrap" }}>
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
    </div>
  );
}
