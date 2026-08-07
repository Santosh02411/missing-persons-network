import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  Bell,
  ChevronDown,
  FilePlus2,
  LayoutDashboard,
  LogOut,
  Search,
  Shield,
  ShieldCheck,
  User,
} from "lucide-react";
import { resendVerification } from "../api/auth";
import { useAuth } from "../context/AuthContext";

const DASHBOARD_BY_ROLE = {
  reporter: { to: "/dashboard/citizen", label: "My dashboard", icon: LayoutDashboard },
  authority: { to: "/dashboard/authority", label: "Authority queue", icon: ShieldCheck },
  admin: { to: "/dashboard/admin", label: "Admin", icon: Shield },
};

function getInitials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] || "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase();
}

function navLinkClass({ isActive }) {
  return `nav-link${isActive ? " active" : ""}`;
}

export default function Masthead() {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [scrolled, setScrolled] = useState(false);
  const [openMenu, setOpenMenu] = useState(null); // "notif" | "profile" | null
  const [resendState, setResendState] = useState("idle"); // idle | sending | sent
  const menuRef = useRef(null);

  // Masthead lives outside <Routes> and never unmounts, so an open dropdown
  // would otherwise stay open across a navigation triggered by one of its
  // own links.
  useEffect(() => {
    setOpenMenu(null);
  }, [location.pathname]);

  useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > 8);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!openMenu) return undefined;
    function onPointerDown(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOpenMenu(null);
      }
    }
    function onKeyDown(e) {
      if (e.key === "Escape") setOpenMenu(null);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [openMenu]);

  async function handleLogout() {
    setOpenMenu(null);
    await logout();
    navigate("/");
  }

  async function handleResend() {
    setResendState("sending");
    try {
      await resendVerification();
      setResendState("sent");
    } catch {
      setResendState("idle");
    }
  }

  const dashboard = isAuthenticated ? DASHBOARD_BY_ROLE[user.role] : null;
  const DashboardIcon = dashboard?.icon;
  const needsEmailVerification = isAuthenticated && !user.email_verified;

  return (
    <header className={`masthead${scrolled ? " scrolled" : ""}`}>
      <div className="container masthead-inner">
        <Link to="/" className="masthead-brand">
          <span className="masthead-logo" aria-hidden="true">
            <ShieldCheck size={19} strokeWidth={2.25} />
          </span>
          <span>
            <span className="masthead-eyebrow">National Missing Persons Registry</span>
            <span className="masthead-title">Reunification Network</span>
          </span>
        </Link>

        {isAuthenticated ? (
          <div className="masthead-right" ref={menuRef}>
            <nav className="masthead-nav">
              <NavLink to="/" end className={navLinkClass}>
                <Search size={15} aria-hidden="true" /> Browse cases
              </NavLink>
              <NavLink to="/cases/new" className={navLinkClass}>
                <FilePlus2 size={15} aria-hidden="true" /> File a case
              </NavLink>
              {dashboard && (
                <NavLink to={dashboard.to} className={navLinkClass}>
                  <DashboardIcon size={15} aria-hidden="true" /> {dashboard.label}
                </NavLink>
              )}
              {user.role === "admin" && (
                <NavLink to="/dashboard/authority" className={navLinkClass}>
                  <ShieldCheck size={15} aria-hidden="true" /> Authority queue
                </NavLink>
              )}
            </nav>

            <div className="masthead-actions">
              <div className="dropdown-wrap">
                <button
                  type="button"
                  className="icon-btn"
                  aria-label="Notifications"
                  aria-expanded={openMenu === "notif"}
                  onClick={() => setOpenMenu((m) => (m === "notif" ? null : "notif"))}
                >
                  <Bell size={18} aria-hidden="true" />
                  {needsEmailVerification && <span className="notif-dot" aria-hidden="true" />}
                </button>
                {openMenu === "notif" && (
                  <div className="dropdown" role="menu">
                    <div className="dropdown-header">Notifications</div>
                    {needsEmailVerification ? (
                      <div className="dropdown-item dropdown-item-static">
                        <div style={{ width: "100%" }}>
                          <strong>Verify your email</strong>
                          <p className="field-hint" style={{ margin: "2px 0 8px" }}>
                            Confirm your address to help secure your account.
                          </p>
                          <button
                            type="button"
                            className="btn btn-secondary"
                            style={{ padding: "4px 10px", fontSize: "0.78rem" }}
                            onClick={handleResend}
                            disabled={resendState !== "idle"}
                          >
                            {resendState === "sent"
                              ? "Email sent"
                              : resendState === "sending"
                                ? "Sending…"
                                : "Resend email"}
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="dropdown-empty">
                        <Bell size={18} aria-hidden="true" />
                        <span>Nothing pending</span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="dropdown-wrap">
                <button
                  type="button"
                  className="avatar-btn"
                  aria-label="Account menu"
                  aria-expanded={openMenu === "profile"}
                  onClick={() => setOpenMenu((m) => (m === "profile" ? null : "profile"))}
                >
                  <span className="avatar" aria-hidden="true">
                    {getInitials(user.full_name)}
                  </span>
                  <ChevronDown size={14} aria-hidden="true" />
                </button>
                {openMenu === "profile" && (
                  <div className="dropdown" role="menu">
                    <div className="dropdown-header">
                      <div style={{ fontWeight: 600 }}>{user.full_name}</div>
                      <div className="mono field-hint" style={{ margin: 0 }}>
                        {user.email}
                      </div>
                    </div>
                    <Link to="/profile" className="dropdown-item" onClick={() => setOpenMenu(null)}>
                      <User size={16} aria-hidden="true" /> My profile
                    </Link>
                    <Link
                      to="/account/security"
                      className="dropdown-item"
                      onClick={() => setOpenMenu(null)}
                    >
                      <Shield size={16} aria-hidden="true" /> Account security
                    </Link>
                    <div className="dropdown-divider" />
                    <button type="button" className="dropdown-item dropdown-item-danger" onClick={handleLogout}>
                      <LogOut size={16} aria-hidden="true" /> Log out
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          <nav className="masthead-nav">
            <Link to="/login" className="nav-link">
              Log in
            </Link>
            <Link to="/register" className="btn btn-primary" style={{ padding: "8px 16px" }}>
              Register
            </Link>
          </nav>
        )}
      </div>
    </header>
  );
}
