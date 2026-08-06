import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

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
  const { user } = useAuth();
  const dashboard = DASHBOARD_LINKS[user.role];

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
