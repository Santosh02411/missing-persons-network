import { useEffect, useState } from "react";
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
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    function onScroll() {
      setIsScrolled(window.scrollY > 8);
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  async function handleLogout() {
    await logout();
    navigate("/");
  }

  const dashboard = isAuthenticated ? DASHBOARD_BY_ROLE[user.role] : null;

  return (
    <header className={`masthead${isScrolled ? " is-scrolled" : ""}`}>
      <div className="container masthead-inner">
        <Link to="/" className="masthead-brand" style={{ textDecoration: "none" }}>
          {/* beacon mark: a lighthouse-like signal, standing in for
              "a light kept on" rather than a generic shield/badge icon */}
          <svg className="masthead-mark" viewBox="0 0 32 32" fill="none" aria-hidden="true">
            <path d="M16 3l4 6h-8l4-6z" fill="currentColor" />
            <path d="M13 9h6l1.5 18h-9L13 9z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
            <path d="M12.2 15h7.6M11.6 20h8.8" stroke="currentColor" strokeWidth="1.2" opacity="0.7" />
            <circle cx="16" cy="3" r="1.4" fill="currentColor" />
          </svg>
          <div>
            <div className="masthead-eyebrow">National Missing Persons Registry</div>
            <h1 className="masthead-title">Reunification Network</h1>
          </div>
        </Link>

        <nav className="masthead-nav">
          {isAuthenticated ? (
            <>
              <Link to="/">Browse cases</Link>
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
              <Link to="/cases/new" className="masthead-cta">
                File a case
              </Link>
            </>
          ) : (
            <>
              <Link to="/login">Log in</Link>
              <Link to="/register" className="masthead-cta">
                Register
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
