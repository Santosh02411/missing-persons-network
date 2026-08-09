import { Link } from "react-router-dom";

export default function ReunitedCard({ caseItem }) {
  return (
    <Link to={`/cases/${caseItem.id}`} className="case-card reunited-card" style={{ textDecoration: "none" }}>
      <div className="status-ribbon reunited-ribbon" aria-hidden="true" />
      <div className="case-card-photo-wrap">
        {caseItem.photo_url ? (
          <img src={caseItem.photo_url} alt={caseItem.name} className="case-card-photo" />
        ) : (
          <div className="case-card-photo-placeholder">No photo provided</div>
        )}
      </div>
      <div className="case-card-body">
        <div className="case-card-top">
          <div className="case-card-name">{caseItem.name}</div>
        </div>
        <span className="status-badge reunited-badge">Reunited</span>
        <div className="case-card-meta">Last seen: {caseItem.last_seen_address}</div>
      </div>
    </Link>
  );
}
