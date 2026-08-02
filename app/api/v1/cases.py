import json
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.cache import CASES_LIST_TTL_SECONDS, cases_list_cache_key
from app.core.deps import get_current_user, require_verified_authority_or_admin
from app.core.redis_client import redis_client
from app.db.session import get_db
from app.models.case import CaseStatus
from app.models.user import User
from app.schemas.case import CaseCreate, CaseListItem, CaseRead, CaseStatusUpdate, CaseUpdate
from app.schemas.geo import GeoPoint
from app.services import case_service
from app.services.geo_service import nearby_cases

router = APIRouter()


@router.post("", response_model=CaseRead, status_code=201)
def create_case(
    payload: CaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseRead:
    case = case_service.create_case(db, payload, reporter=current_user)
    return CaseRead.model_validate(case)


@router.get("", response_model=list[CaseListItem])
def list_cases(
    status_filter: CaseStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[CaseListItem]:
    """Public -- browse cases. No auth required, matches FR-5.

    Cached in Redis for CASES_LIST_TTL_SECONDS. The cache key includes a
    version number (see core/cache.py) that's bumped on any case write, so
    stale results aren't served past the next create/edit/claim/status-change
    -- the TTL is a backstop for read load, not the primary invalidation
    mechanism.
    """
    cache_key = cases_list_cache_key(
        status_filter.value if status_filter else None, limit, offset
    )
    cached = redis_client.get(cache_key)
    if cached is not None:
        return json.loads(cached)

    cases = case_service.list_cases(db, status_filter, limit, offset)
    result = [CaseListItem.model_validate(c).model_dump(mode="json") for c in cases]
    redis_client.set(cache_key, json.dumps(result), ex=CASES_LIST_TTL_SECONDS)
    return result


@router.get("/nearby", response_model=list[CaseListItem])
def get_nearby_cases(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=10, gt=0, le=500),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[CaseListItem]:
    """FR-11: open cases whose last-seen location is within radius_km of
    (lat, lng), nearest first. Must be registered before /{case_id} below --
    otherwise FastAPI would try to parse "nearby" as a case_id and 422."""
    center = GeoPoint(lat=lat, lng=lng)
    cases = nearby_cases(db, center, radius_km, limit)
    return [CaseListItem.model_validate(c) for c in cases]


@router.get("/assigned-to-me", response_model=list[CaseRead])
def get_assigned_cases(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_authority_or_admin),
) -> list[CaseRead]:
    """Backs the authority dashboard's "my cases" list. Registered before
    /{case_id} for the same reason /nearby is -- otherwise FastAPI tries to
    parse "assigned-to-me" as a case UUID and 422s."""
    cases = case_service.list_assigned_cases(db, current_user.id)
    return [CaseRead.model_validate(c) for c in cases]


@router.get("/{case_id}", response_model=CaseRead)
def get_case(case_id: uuid.UUID, db: Session = Depends(get_db)) -> CaseRead:
    """Public -- case detail. No auth required, matches FR-5."""
    case = case_service.get_case_or_404(db, case_id)
    return CaseRead.model_validate(case)


@router.patch("/{case_id}", response_model=CaseRead)
def update_case(
    case_id: uuid.UUID,
    payload: CaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseRead:
    """Row-level check inside case_service.update_case: reporter (owner),
    assigned authority, or admin only."""
    case = case_service.get_case_or_404(db, case_id)
    updated = case_service.update_case(db, case, payload, current_user)
    return CaseRead.model_validate(updated)


@router.post("/{case_id}/claim", response_model=CaseRead)
def claim_case(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_authority_or_admin),
) -> CaseRead:
    """A verified authority takes ownership of a case. FR-3. Restricted to
    verified authority/admin roles -- an unverified authority account can't
    claim cases yet."""
    case = case_service.get_case_or_404(db, case_id)
    updated = case_service.claim_case(db, case, actor=current_user)
    return CaseRead.model_validate(updated)


@router.patch("/{case_id}/status", response_model=CaseRead)
def update_case_status(
    case_id: uuid.UUID,
    payload: CaseStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_authority_or_admin),
) -> CaseRead:
    """Restricted to verified authority/admin at the route level; further
    restricted to *this case's* assigned authority (or admin) at the row
    level inside case_service.update_case_status."""
    case = case_service.get_case_or_404(db, case_id)
    updated = case_service.update_case_status(db, case, payload.status, actor=current_user)
    return CaseRead.model_validate(updated)
