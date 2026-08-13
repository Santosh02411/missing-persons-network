import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.email import send_email
from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.case_collaborator import CaseCollaborator
from app.models.sighting import Sighting, SightingStatus
from app.models.user import User, UserRole
from app.schemas.sighting import SightingCreate
from app.services import case_service, face_match_service, watch_service
from app.services.geo_service import to_geography
from app.services.upload_service import read_upload_bytes

logger = logging.getLogger("app.sightings")


def _compute_photo_match_score(case: Case, sighting_photo_url: str | None) -> float | None:
    """Best-effort face-similarity score between the sighting's photo and
    the case's photo -- see face_match_service for the method and its
    tradeoffs. Never raises: a decode/detection failure just means no score,
    same as either photo being absent, and must not block the sighting from
    being submitted."""
    case_bytes = read_upload_bytes(case.photo_url)
    sighting_bytes = read_upload_bytes(sighting_photo_url)
    if case_bytes is None or sighting_bytes is None:
        return None
    try:
        result = face_match_service.match_faces(case_bytes, sighting_bytes)
    except Exception:
        logger.exception("Face-match scoring failed for case %s", case.id)
        return None
    return result["score"]


def get_reporter_stats_bulk(db: Session, reporter_ids: list) -> dict:
    """Sighting accuracy history for a set of reporters in one query --
    counts of their past sightings by outcome (verified / dismissed /
    still pending), so an authority reviewing a new sighting can weigh it
    against "this person's last 10 reports were all verified" vs "this
    person's last 5 were all dismissed." Authority-facing only (see
    SightingQueueItem, the only schema this is attached to) -- never shown
    to the reporter themselves or the public, since a visible "credibility
    score" would invite gaming it rather than reporting honestly.

    Returns {reporter_id: {"verified": n, "dismissed": n, "pending": n, "total": n}}
    for every id in reporter_ids, including zeroed entries for reporters
    with no history yet -- callers shouldn't need a .get() with a default.
    """
    stats = {
        rid: {"verified": 0, "dismissed": 0, "pending": 0, "total": 0} for rid in reporter_ids
    }
    if not reporter_ids:
        return stats
    stmt = (
        select(Sighting.reported_by, Sighting.status, func.count())
        .where(Sighting.reported_by.in_(reporter_ids))
        .group_by(Sighting.reported_by, Sighting.status)
    )
    for reporter_id, sighting_status, count in db.execute(stmt):
        entry = stats[reporter_id]
        entry[sighting_status.value] = count
        entry["total"] += count
    return stats


def list_pending_sightings(
    db: Session, actor: User, limit: int = 50, offset: int = 0
) -> list[Sighting]:
    """Pending-review queue for the authority dashboard, scoped the same way
    as case approval/status changes: a non-admin authority only sees
    sightings on cases they have access to (the case's assigned authority,
    or a collaborator on it) -- not every pending sighting nationwide.
    Cases with no assigned authority yet (never claimed/approved) still show
    up for every verified authority, matching the same fallback used for
    unrouted cases in list_pending_approval_cases, so a sighting never sits
    unreviewable just because its case hasn't been claimed. Admins see
    everything, for oversight. Eager-loads the parent case (joinedload) so
    the route can attach case_name to each item without an extra query per
    row."""
    stmt = (
        select(Sighting)
        .join(Case, Sighting.case_id == Case.id)
        .options(joinedload(Sighting.case))
        .where(Sighting.status == SightingStatus.PENDING)
    )
    if actor.role != UserRole.ADMIN:
        collaborator_case_ids = select(CaseCollaborator.case_id).where(
            CaseCollaborator.user_id == actor.id
        )
        stmt = stmt.where(
            (Case.assigned_authority_id == actor.id)
            | (Case.assigned_authority_id.is_(None))
            | (Case.id.in_(collaborator_case_ids))
        )
    stmt = stmt.order_by(Sighting.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


def _notify_station_of_new_sighting(db: Session, case: Case, sighting: Sighting) -> None:
    """Emails everyone with access to this case (the assigned authority plus
    any collaborators -- see case_service.list_case_access_user_ids) the
    moment a new sighting comes in, rather than only relying on someone
    checking the pending-sightings queue. Best-effort: a failure here must
    never block the sighting submission itself."""
    user_ids = case_service.list_case_access_user_ids(db, case)
    if not user_ids:
        return
    stmt = select(User).where(User.id.in_(user_ids), User.is_active.is_(True))
    recipients = list(db.scalars(stmt))
    if not recipients:
        return

    case_url = f"{settings.FRONTEND_URL.rstrip('/')}/cases/{case.id}"
    body = (
        f"A new sighting was just reported on a case you're handling.\n\n"
        f"Case: {case.name}\n"
        f"Reported near: {sighting.address_text}\n"
        f"Details: {sighting.description}\n\n"
        f"Review it here: {case_url}\n\n"
        "You're getting this because you're the assigned authority or a "
        "collaborator on this case."
    )
    for recipient in recipients:
        try:
            send_email(
                to=recipient.email,
                subject=f"New sighting reported: {case.name}",
                body=body,
            )
        except Exception:
            logger.exception(
                "Failed to notify %s of new sighting on case %s", recipient.id, case.id
            )


def create_sighting(db: Session, payload: SightingCreate, reporter: User | None) -> Sighting:
    case = db.get(Case, payload.case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    sighting = Sighting(
        case_id=payload.case_id,
        reported_by=reporter.id if reporter else None,
        location=to_geography(payload.location),
        address_text=payload.address_text,
        description=payload.description,
        photo_url=payload.photo_url,
        status=SightingStatus.PENDING,
        photo_match_score=_compute_photo_match_score(case, payload.photo_url),
    )
    db.add(sighting)
    db.commit()
    db.refresh(sighting)
    _notify_station_of_new_sighting(db, case, sighting)
    return sighting


def get_sighting_or_404(db: Session, sighting_id: uuid.UUID) -> Sighting:
    sighting = db.get(Sighting, sighting_id)
    if sighting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sighting not found")
    return sighting


def list_sightings_for_case(db: Session, case_id: uuid.UUID) -> list[Sighting]:
    stmt = (
        select(Sighting)
        .where(Sighting.case_id == case_id)
        .order_by(Sighting.created_at.desc())
    )
    return list(db.scalars(stmt))


def list_my_sightings(db: Session, user_id) -> list[Sighting]:
    """All sightings reported by this user -- backs the citizen dashboard's
    "my sightings" list."""
    stmt = (
        select(Sighting)
        .where(Sighting.reported_by == user_id)
        .order_by(Sighting.created_at.desc())
    )
    return list(db.scalars(stmt))


def review_sighting(
    db: Session, sighting: Sighting, new_status: SightingStatus, reviewer: User
) -> Sighting:
    # Role check (verified authority/admin) happens at the route level via
    # require_verified_authority_or_admin. Row-level: only the case's
    # assigned authority, a collaborator on that case, or an admin may
    # review a sighting on it -- same rule as case status changes (see
    # case_service.has_case_access) -- unless the case has no assigned
    # authority yet, which stays open to any verified authority, matching
    # the same fallback used for unrouted cases (see list_pending_sightings).
    case = db.get(Case, sighting.case_id)
    has_access = case is not None and (
        case.assigned_authority_id is None or case_service.has_case_access(db, case, reviewer)
    )
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned authority, a collaborator on this case, or an admin can review this sighting",
        )
    if new_status == SightingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'pending' is not a valid review outcome",
        )

    sighting.status = new_status
    sighting.reviewed_by = reviewer.id
    sighting.reviewed_at = datetime.now(timezone.utc)

    db.add(
        AuditLog(
            actor_id=reviewer.id,
            action="sighting.reviewed",
            target_type="sighting",
            target_id=sighting.id,
            log_metadata={"outcome": new_status.value},
        )
    )
    db.commit()
    db.refresh(sighting)
    if new_status == SightingStatus.VERIFIED:
        watch_service.notify_watchers(
            db, case,
            headline="A new sighting has been verified on this case.",
            detail=f"Reported near: {sighting.address_text}",
            exclude_user_id=reviewer.id,
        )
    return sighting
