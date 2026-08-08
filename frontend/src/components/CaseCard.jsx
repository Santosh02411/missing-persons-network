import { Link } from "react-router-dom";
import StatusBadge from "./StatusBadge";

export default function CaseCard({ caseItem }) {
  return (
    <Link to={`/cases/${caseItem.id}`} className="case-card" style={{ textDecoration: "none" }}>
      <div className={`status-ribbon status-${caseItem.status}`} aria-hidden="true" />
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
          {caseItem.status === "open" && <span className="beacon-pulse" aria-hidden="true" />}
        </div>
        <StatusBadge status={caseItem.status} />
        <div className="case-card-meta">{caseItem.last_seen_address}</div>
        <div className="case-card-meta">
          Filed {new Date(caseItem.created_at).toLocaleDateString()}
        </div>
      </div>
    </Link>
  );
}
