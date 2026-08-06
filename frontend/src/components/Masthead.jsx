import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const DASHBOARD_BY_ROLE = {
  reporter: { to: "/dashboard/citizen", label: "My dashboard" },
  authority: { to: "/dashboard/authority", label: "Authority queue" },
  admin: { to: "/dashboard/admin", label: "Admin" },
};

export default function Masthead() {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/");
  }

  const dashboard = isAuthenticated ? DASHBOARD_BY_ROLE[user.role] : null;

  return (
    <header className="masthead">
      <div className="container masthead-inner">
        <Link to="/" style={{ textDecoration: "none" }}>
          <div className="masthead-eyebrow">National Missing Persons Registry</div>
          <h1 className="masthead-title">Reunification Network</h1>
        </Link>

        <nav className="masthead-nav">
          {isAuthenticated ? (
            <>
              <Link to="/">Browse cases</Link>
              <Link to="/cases/new">File a case</Link>
              {dashboard && <Link to={dashboard.to}>{dashboard.label}</Link>}
              {user.role === "admin" && (
                <Link to="/dashboard/authority">Authority queue</Link>
              )}
              <Link to="/profile" className="masthead-user">
                {user.full_name}
              </Link>
              <button onClick={handleLogout} style={{ background: "none", border: "none", cursor: "pointer" }}>
                Log out
              </button>
            </>
          ) : (
            <>
              <Link to="/login">Log in</Link>
              <Link to="/register">Register</Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
