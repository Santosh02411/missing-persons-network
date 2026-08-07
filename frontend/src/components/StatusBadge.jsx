import { CheckCircle2, Clock, Lightbulb, Search, ShieldCheck, XCircle } from "lucide-react";

// Labels are unchanged from before this redesign -- only the visual
// treatment (pill shape, color, icon) changed. Every consumer of this
// component across the app (case cards, case detail, dashboards, profile)
// picks up the icon for free.
const CONFIG = {
  pending_review: { label: "Awaiting approval", icon: Clock },
  open: { label: "Open", icon: Search },
  lead_found: { label: "Lead found", icon: Lightbulb },
  resolved: { label: "Resolved", icon: CheckCircle2 },
  dismissed: { label: "Dismissed", icon: XCircle },
  pending: { label: "Pending review", icon: Clock },
  verified: { label: "Verified", icon: ShieldCheck },
};

export default function StatusBadge({ status }) {
  const config = CONFIG[status];
  const Icon = config?.icon;
  return (
    <span className={`status-badge status-${status}`}>
      {Icon && <Icon size={12} strokeWidth={2.5} aria-hidden="true" />}
      {config ? config.label : status}
    </span>
  );
}
