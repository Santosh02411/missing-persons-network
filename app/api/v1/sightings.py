import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_current_user_optional
from app.db.session import get_db
from app.models.user import User
from app.schemas.sighting import SightingCreate, SightingRead, SightingReview
from app.services import sighting_service

router = APIRouter()


@router.post("", response_model=SightingRead, status_code=201)
def submit_sighting(
    payload: SightingCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> SightingRead:
    """Public — anonymous tips are allowed (FR-6). If a valid access token is
    provided the sighting is attributed to that user; otherwise reported_by is null.

    NOTE (Phase 4): this endpoint gets a tight Redis rate limit
    (SIGHTING_REPORT_RATE_LIMIT) — not yet applied here."""
    sighting = sighting_service.create_sighting(db, payload, reporter=current_user)
    return SightingRead.model_validate(sighting)


@router.get("/case/{case_id}", response_model=list[SightingRead])
def list_sightings_for_case(case_id: uuid.UUID, db: Session = Depends(get_db)) -> list[SightingRead]:
    """TODO(phase-3): consider restricting full sighting detail (e.g. reporter
    identity) to authorities — public view may need a slimmer schema."""
    sightings = sighting_service.list_sightings_for_case(db, case_id)
    return [SightingRead.model_validate(s) for s in sightings]


@router.patch("/{sighting_id}/review", response_model=SightingRead)
def review_sighting(
    sighting_id: uuid.UUID,
    payload: SightingReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SightingRead:
    """TODO(phase-3): restrict to verified authority/admin roles via require_role().
    Currently any authenticated user can call this — role enforcement lands in Phase 3."""
    sighting = sighting_service.get_sighting_or_404(db, sighting_id)
    updated = sighting_service.review_sighting(db, sighting, payload.status, reviewer=current_user)
    return SightingRead.model_validate(updated)
