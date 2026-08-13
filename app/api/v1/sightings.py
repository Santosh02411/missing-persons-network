import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_verified_authority_or_admin
from app.core.rate_limit import sighting_rate_limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.geo import GeoPoint
from app.schemas.sighting import SightingCreate, SightingQueueItem, SightingRead, SightingReview
from app.services import sighting_service
from app.services.geo_service import nearby_sightings

router = APIRouter()


@router.post("", response_model=SightingRead, status_code=201, dependencies=[Depends(sighting_rate_limiter)])
def submit_sighting(
    payload: SightingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SightingRead:
    """Requires login (anonymous tips are no longer accepted -- every
    sighting report is attributed to an identifiable account).

    Rate-limited (FR-7): sighting_rate_limiter enforces
    SIGHTING_REPORT_RATE_LIMIT (default 5/minute), keyed by user id.
    Returns 429 with a Retry-After header when exceeded."""
    sighting = sighting_service.create_sighting(db, payload, reporter=current_user)
    return SightingRead.model_validate(sighting)


@router.get("/nearby", response_model=list[SightingRead])
def get_nearby_sightings(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=5, gt=0, le=500),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SightingRead]:
    """FR-10: sightings within radius_km of (lat, lng), nearest first.
    Requires login, same as case browsing. Registered before
    /{sighting_id}-style routes aren't an issue here since this file has no
    bare /{id} path (only /case/{case_id} and /{id}/review), but kept early
    in the file for consistency with cases.py."""
    center = GeoPoint(lat=lat, lng=lng)
    sightings = nearby_sightings(db, center, radius_km, limit)
    return [SightingRead.model_validate(s) for s in sightings]


@router.get("/mine", response_model=list[SightingRead])
def get_my_sightings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SightingRead]:
    """Backs the citizen dashboard's "my sightings" list."""
    sightings = sighting_service.list_my_sightings(db, current_user.id)
    return [SightingRead.model_validate(s) for s in sightings]


@router.get("/pending", response_model=list[SightingQueueItem])
def get_pending_sightings(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_authority_or_admin),
) -> list[SightingQueueItem]:
    """Pending-review queue for the authority dashboard -- scoped to cases
    the current authority has access to (see sighting_service.list_pending_
    sightings); admins see everything."""
    sightings = sighting_service.list_pending_sightings(db, current_user, limit, offset)
    reporter_ids = [s.reported_by for s in sightings if s.reported_by is not None]
    stats_by_reporter = sighting_service.get_reporter_stats_bulk(db, reporter_ids)
    items = []
    for s in sightings:
        data = SightingRead.model_validate(s).model_dump()
        data["case_name"] = s.case.name
        data["reporter_stats"] = stats_by_reporter.get(s.reported_by) if s.reported_by else None
        items.append(data)
    return items


@router.get("/case/{case_id}", response_model=list[SightingRead])
def list_sightings_for_case(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SightingRead]:
    """Requires login, matching case detail visibility."""
    sightings = sighting_service.list_sightings_for_case(db, case_id)
    return [SightingRead.model_validate(s) for s in sightings]


@router.patch("/{sighting_id}/review", response_model=SightingRead)
def review_sighting(
    sighting_id: uuid.UUID,
    payload: SightingReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_authority_or_admin),
) -> SightingRead:
    """Restricted to verified authority/admin accounts."""
    sighting = sighting_service.get_sighting_or_404(db, sighting_id)
    updated = sighting_service.review_sighting(db, sighting, payload.status, reviewer=current_user)
    return SightingRead.model_validate(updated)
