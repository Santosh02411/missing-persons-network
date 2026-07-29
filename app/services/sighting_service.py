import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.sighting import Sighting, SightingStatus
from app.models.user import User
from app.schemas.sighting import SightingCreate
from app.services.geo_service import to_geography


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
    return sighting
