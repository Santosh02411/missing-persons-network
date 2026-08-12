"""Case timeline: a single chronological view of what's happened on a case
-- filed, approved, status changes, sightings reported/reviewed, dismissed
-- built from data already recorded (case/sighting rows + the audit log)
rather than a new table, since nothing here needs to be written, only
assembled and ordered.

Two detail levels, decided by who's asking:
  - Full: the case's reporter, anyone with case access (assigned authority,
    a collaborator, or admin -- see case_service.has_case_access), or an
    admin. Includes internal-only events (sharing, collaborators added/
    removed, dismiss reasons).
  - Public: everyone else who can view the case at all (i.e. the case is
    OPEN/LEAD_FOUND/RESOLVED). Investigation-internal events are left out,
    same privacy boundary as case notes.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.sighting import Sighting
from app.models.user import User
from app.services.case_service import has_case_access

# Event types only ever shown to someone with full case access -- these
# describe internal coordination, not the case's public-facing history.
_INTERNAL_ONLY_ACTIONS = {"case.shared", "case.collaborator_added", "case.collaborator_removed"}


def _case_event_label(log: AuditLog) -> str:
    meta = log.log_metadata or {}
    if log.action == "case.approved":
        return "Case approved and made public"
    if log.action == "case.claimed":
        return "Case claimed by an authority"
    if log.action == "case.dismissed":
        reason = meta.get("reason")
        return "Case dismissed" + (f" — {reason}" if reason else "")
    if log.action == "case.status_changed":
        to = str(meta.get("to", "")).replace("_", " ").title()
        return f"Status changed to {to}"
    if log.action == "case.reopened":
        reason = meta.get("reason")
        return "Case reopened for further investigation" + (f" — {reason}" if reason else "")
    if log.action == "case.shared":
        return "Shared with another authority"
    if log.action == "case.collaborator_added":
        return "A collaborating authority was added"
    if log.action == "case.collaborator_removed":
        return "A collaborating authority was removed"
    return log.action.replace("_", " ").replace(".", ": ").capitalize()


def _sighting_event_label(log: AuditLog) -> str:
    outcome = (log.log_metadata or {}).get("outcome", "reviewed")
    return f"A sighting was {outcome}"


def get_case_timeline(db: Session, case: Case, viewer: User | None) -> list[dict]:
    full_detail = viewer is not None and (
        case.created_by == viewer.id or has_case_access(db, case, viewer)
    )

    events = [
        {
            "timestamp": case.created_at,
            "type": "case_filed",
            "label": "Case filed",
        }
    ]

    case_logs = db.scalars(
        select(AuditLog)
        .where(AuditLog.target_type == "case", AuditLog.target_id == case.id)
        .order_by(AuditLog.created_at)
    )
    for log in case_logs:
        if not full_detail and log.action in _INTERNAL_ONLY_ACTIONS:
            continue
        events.append({"timestamp": log.created_at, "type": log.action, "label": _case_event_label(log)})

    sightings = list(db.scalars(select(Sighting).where(Sighting.case_id == case.id)))
    for sighting in sightings:
        events.append(
            {
                "timestamp": sighting.created_at,
                "type": "sighting_reported",
                "label": f"A sighting was reported near {sighting.address_text}"
                if full_detail
                else "A sighting was reported",
            }
        )

    sighting_ids = [s.id for s in sightings]
    if sighting_ids:
        sighting_logs = db.scalars(
            select(AuditLog)
            .where(AuditLog.target_type == "sighting", AuditLog.target_id.in_(sighting_ids))
            .order_by(AuditLog.created_at)
        )
        for log in sighting_logs:
            events.append(
                {"timestamp": log.created_at, "type": log.action, "label": _sighting_event_label(log)}
            )

    events.sort(key=lambda e: e["timestamp"])
    return events
