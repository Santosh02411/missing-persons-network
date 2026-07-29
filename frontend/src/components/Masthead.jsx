import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Masthead() {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/");
  }

  return (
    <header className="masthead">
      <div className="container masthead-inner">
        <Link to="/" style={{ textDecoration: "none" }}>
          <div className="masthead-eyebrow">National Missing Persons Registry</div>
          <h1 className="masthead-title">Reunification Network</h1>
        </Link>

        <nav className="masthead-nav">
          <Link to="/">Browse cases</Link>

          {isAuthenticated ? (
            <>
              <Link to="/cases/new">File a case</Link>
              {(user.role === "authority" || user.role === "admin") && (
                <Link to="/dashboard/authority">Authority queue</Link>
              )}
              {user.role === "admin" && <Link to="/dashboard/admin">Admin</Link>}
              <span className="masthead-user">{user.full_name}</span>
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
