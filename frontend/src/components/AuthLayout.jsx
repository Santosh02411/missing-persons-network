const POINTS = [
  {
    title: "File a case in minutes",
    desc: "Families and reporters register a missing person with a photo, last-seen location, and description.",
    icon: (
      <path d="M12 3l7 4v5c0 5-3.5 8.5-7 9-3.5-.5-7-4-7-9V7l7-4z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    ),
  },
  {
    title: "Sightings routed to the right authority",
    desc: "Public sighting reports go straight to the nearest police station or NGO, not a generic inbox.",
    icon: (
      <>
        <circle cx="12" cy="10" r="3" stroke="currentColor" strokeWidth="1.6" />
        <path d="M12 21s7-6.2 7-11a7 7 0 10-14 0c0 4.8 7 11 7 11z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      </>
    ),
  },
  {
    title: "Verified, auditable review",
    desc: "Authorities verify or dismiss every report, with an audit trail and two-factor protected accounts.",
    icon: (
      <path d="M4 12l5 5L20 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    ),
  },
];

export default function AuthLayout({ eyebrow, title, body, children }) {
  return (
    <div className="container">
      <div className="auth-shell">
        <div className="auth-info">
          <div className="auth-info-inner">
            <svg className="auth-info-mark" viewBox="0 0 32 32" fill="none" aria-hidden="true">
              <path d="M16 3l4 6h-8l4-6z" fill="currentColor" />
              <path d="M13 9h6l1.5 18h-9L13 9z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
              <path d="M12.2 15h7.6M11.6 20h8.8" stroke="currentColor" strokeWidth="1.2" opacity="0.7" />
              <circle cx="16" cy="3" r="1.4" fill="currentColor" />
            </svg>
            <div className="auth-info-eyebrow">{eyebrow}</div>
            <h2 className="auth-info-title">{title}</h2>
            <p className="auth-info-body">{body}</p>
            <div className="auth-info-points">
              {POINTS.map((p) => (
                <div className="auth-info-point" key={p.title}>
                  <svg className="auth-info-point-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    {p.icon}
                  </svg>
                  <div>
                    <div className="auth-info-point-title">{p.title}</div>
                    <div className="auth-info-point-desc">{p.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="auth-form-side">
          <div className="form-card">{children}</div>
        </div>
      </div>
    </div>
  );
}
