import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const DASHBOARD_BY_ROLE = {
  reporter: { to: "/dashboard/citizen", label: "My dashboard" },
  authority: { to: "/dashboard/authority", label: "Authority queue" },
  admin: { to: "/dashboard/admin", label: "Admin" },
};

const ROLE_LABELS = {
  reporter: "Citizen / public",
  authority: "Authority",
  admin: "Admin",
};

function initials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] || "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase();
}

export default function Masthead() {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const [isScrolled, setIsScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    function onScroll() {
      setIsScrolled(window.scrollY > 8);
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    function onClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    }
    function onKeyDown(e) {
      if (e.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  async function handleLogout() {
    setMenuOpen(false);
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
              <Link to="/reunited">Reunited</Link>
              {dashboard && <Link to={dashboard.to}>{dashboard.label}</Link>}
              {user.role === "admin" && (
                <Link to="/dashboard/authority">Authority queue</Link>
              )}
              <Link to="/cases/new" className="masthead-cta">
                File a case
              </Link>

              <div className="user-menu" ref={menuRef}>
                <button
                  type="button"
                  className="user-menu-trigger"
                  aria-expanded={menuOpen}
                  aria-haspopup="true"
                  onClick={() => setMenuOpen((v) => !v)}
                >
                  <span className="user-menu-avatar" aria-hidden="true">
                    {initials(user.full_name)}
                  </span>
                  <span className="user-menu-name">{user.full_name}</span>
                  <svg className="user-menu-caret" viewBox="0 0 12 8" fill="none" aria-hidden="true">
                    <path d="M1 1.5l5 5 5-5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>

                {menuOpen && (
                  <div className="user-menu-dropdown" role="menu">
                    <div className="user-menu-header">
                      <div className="user-menu-header-name">{user.full_name}</div>
                      <div className="user-menu-header-role">{ROLE_LABELS[user.role] || user.role}</div>
                    </div>
                    <Link to="/profile" className="user-menu-item" role="menuitem" onClick={() => setMenuOpen(false)}>
                      My profile
                    </Link>
                    <Link
                      to="/account/security"
                      className="user-menu-item"
                      role="menuitem"
                      onClick={() => setMenuOpen(false)}
                    >
                      Security settings
                    </Link>
                    <button type="button" className="user-menu-item danger" role="menuitem" onClick={handleLogout}>
                      Log out
                    </button>
                  </div>
                )}
              </div>
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
