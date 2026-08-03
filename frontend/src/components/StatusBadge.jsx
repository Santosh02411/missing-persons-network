const LABELS = {
  pending_review: "Awaiting approval",
  open: "Open",
  lead_found: "Lead found",
  resolved: "Resolved",
  pending: "Pending review",
  verified: "Verified",
  dismissed: "Dismissed",
};

export default function StatusBadge({ status }) {
  return <span className={`status-badge status-${status}`}>{LABELS[status] || status}</span>;
}
