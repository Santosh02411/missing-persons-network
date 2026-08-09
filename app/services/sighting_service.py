import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.sighting import Sighting, SightingStatus
from app.models.user import User
from app.schemas.sighting import SightingCreate
from app.services import face_match_service, watch_service
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


def list_pending_sightings(db: Session, limit: int = 50, offset: int = 0) -> list[Sighting]:
    """Global pending-review queue -- backs the authority dashboard. Eager-
    loads the parent case (joinedload) so the route can attach case_name to
    each item without an extra query per row."""
    stmt = (
        select(Sighting)
        .options(joinedload(Sighting.case))
        .where(Sighting.status == SightingStatus.PENDING)
        .order_by(Sighting.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))


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
    # require_verified_authority_or_admin. No row-level ownership constraint
    # here by design -- any verified authority can review any pending sighting,
    # unlike case status changes which are scoped to the assigned authority.
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
        case = db.get(Case, sighting.case_id)
        if case is not None:
            watch_service.notify_watchers(
                db, case,
                headline="A new sighting has been verified on this case.",
                detail=f"Reported near: {sighting.address_text}",
                exclude_user_id=reviewer.id,
            )
    return sighting
