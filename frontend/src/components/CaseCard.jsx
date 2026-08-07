import { useState } from "react";
import { Link } from "react-router-dom";
import { Eye, MapPin, MessageSquare, Share2 } from "lucide-react";
import StatusBadge from "./StatusBadge";

export default function CaseCard({ caseItem }) {
  const [shareState, setShareState] = useState("idle"); // idle | copied
  const detailUrl = `/cases/${caseItem.id}`;

  async function handleShare() {
    const fullUrl = `${window.location.origin}${detailUrl}`;
    if (navigator.share) {
      try {
        await navigator.share({ title: caseItem.name, url: fullUrl });
      } catch {
        // Cancelling the native share sheet throws -- not an error, just no-op.
      }
      return;
    }
    try {
      await navigator.clipboard.writeText(fullUrl);
      setShareState("copied");
      setTimeout(() => setShareState("idle"), 2000);
    } catch {
      // Clipboard access blocked -- nothing meaningful to recover here.
    }
  }

  return (
    <div className="case-card">
      {/* Decorative duplicate of the name link below -- aria-hidden so
          screen readers/keyboard users get one link per card, not two. */}
      <Link to={detailUrl} className="case-card-media" tabIndex={-1} aria-hidden="true">
        {caseItem.photo_url ? (
          <img src={caseItem.photo_url} alt="" className="case-card-photo" />
        ) : (
          <div className="case-card-photo-placeholder">No photo provided</div>
        )}
        <span className="case-card-badge">
          <StatusBadge status={caseItem.status} />
        </span>
      </Link>

      <div className="case-card-body">
        <Link to={detailUrl} className="case-card-name">
          {caseItem.name}
        </Link>
        <div className="case-card-meta-row">
          <MapPin size={13} aria-hidden="true" />
          <span>{caseItem.last_seen_address}</span>
        </div>
        <div className="case-card-meta-row case-card-meta-sub">
          <span>Filed {new Date(caseItem.created_at).toLocaleDateString()}</span>
          <span>#{caseItem.id.slice(0, 8)}</span>
        </div>
      </div>

      <div className="case-card-actions">
        <Link to={detailUrl} className="card-action-btn">
          <Eye size={14} aria-hidden="true" /> View
        </Link>
        <button type="button" className="card-action-btn" onClick={handleShare}>
          <Share2 size={14} aria-hidden="true" /> {shareState === "copied" ? "Copied!" : "Share"}
        </button>
        <Link to={detailUrl} className="card-action-btn">
          <MessageSquare size={14} aria-hidden="true" /> Report
        </Link>
      </div>
    </div>
  );
}
