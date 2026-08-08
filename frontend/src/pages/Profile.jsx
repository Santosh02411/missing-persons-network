import { useState } from "react";
import { Link } from "react-router-dom";
import { updateJurisdiction } from "../api/auth";
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
              : "Not enabled"}
        </div>

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
