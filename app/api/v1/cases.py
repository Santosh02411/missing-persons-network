import json
import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.cache import CASES_LIST_TTL_SECONDS, cases_list_cache_key
from app.core.deps import get_current_user, require_verified_authority_or_admin
from app.core.redis_client import redis_client
from app.db.session import get_db
from app.models.case import CaseStatus
from app.models.user import User
from app.schemas.case import CaseCreate, CaseListItem, CaseRead, CaseShareRequest, CaseStatusUpdate, CaseUpdate
from app.schemas.geo import GeoPoint
from app.schemas.watch import WatchStatus
from app.services import case_service, flyer_service, watch_service
from app.services.geo_service import nearby_cases

router = APIRouter()


@router.post("", response_model=CaseRead, status_code=201)
def create_case(
    payload: CaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseRead:
    """New cases start as pending_review -- not publicly listed until an
    authority approves them (see POST /{case_id}/approve). The reporter can
    still view their own case's detail page while it's pending."""
    case = case_service.create_case(db, payload, reporter=current_user)
    return CaseRead.model_validate(case)


@router.get("", response_model=list[CaseListItem])
def list_cases(
    status_filter: CaseStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CaseListItem]:
    """Requires login -- browsing cases is restricted to registered users
    (any role) so that filing/viewing/sharing case info always happens under
    an identifiable account, not anonymously. Never includes pending_review
    or dismissed cases -- see case_service.list_cases().

    Cached in Redis for CASES_LIST_TTL_SECONDS. The cache key includes a
    version number (see core/cache.py) that's bumped on any case write, so
    stale results aren't served past the next create/edit/claim/status-change
    -- the TTL is a backstop for read load, not the primary invalidation
    mechanism. The cache itself isn't user-specific (the same approved-cases
    list is the same for every logged-in viewer), so it's safe to share
    across users despite the endpoint now requiring auth.
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
    current_user: User = Depends(get_current_user),
) -> list[CaseListItem]:
    """FR-11: open cases whose last-seen location is within radius_km of
    (lat, lng), nearest first. Requires login, same as the plain list above.
    Must be registered before /{case_id} below -- otherwise FastAPI would
    try to parse "nearby" as a case_id and 422."""
    center = GeoPoint(lat=lat, lng=lng)
    cases = nearby_cases(db, center, radius_km, limit)
    return [CaseListItem.model_validate(c) for c in cases]


@router.get("/mine", response_model=list[CaseRead])
def get_my_cases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CaseRead]:
    """Backs the citizen dashboard's "my cases" list -- every case this user
    filed, at any status (including pending_review and dismissed), so they
    can track what happened to their own submissions. Registered before
    /{case_id} for the usual routing-order reason."""
    cases = case_service.list_my_cases(db, current_user.id)
    return [CaseRead.model_validate(c) for c in cases]


@router.get("/watched", response_model=list[CaseRead])
def get_watched_cases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CaseRead]:
    """Backs the citizen dashboard's "cases I'm watching" section --
    everything this user has subscribed to for email updates, regardless of
    whether they filed it themselves. Registered before /{case_id} for the
    usual routing-order reason."""
    cases = watch_service.list_watched_cases(db, current_user.id)
    return [CaseRead.model_validate(c) for c in cases]


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


@router.get("/pending-approval", response_model=list[CaseRead])
def get_pending_approval_cases(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_authority_or_admin),
) -> list[CaseRead]:
    """Backs the authority dashboard's approval queue -- newly filed cases
    waiting to be reviewed before they go public. Registered before
    /{case_id} for the same routing-order reason as /nearby above."""
    cases = case_service.list_pending_approval_cases(db, current_user, limit, offset)
    return [CaseRead.model_validate(c) for c in cases]


@router.get("/{case_id}", response_model=CaseRead)
def get_case(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseRead:
    """Requires login for any case. A pending_review or dismissed case is
    further restricted to the reporter who filed it or an authority/admin --
    see case_service.get_case_or_404's visibility check."""
    case = case_service.get_case_or_404(db, case_id, current_user)
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
    case = case_service.get_case_or_404(db, case_id, current_user)
    updated = case_service.update_case(db, case, payload, current_user)
    return CaseRead.model_validate(updated)


@router.post("/{case_id}/approve", response_model=CaseRead)
def approve_case(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_authority_or_admin),
) -> CaseRead:
    """A verified authority (or admin) approves a newly-filed case, making it
    publicly visible and simultaneously claiming it -- the reviewing
    authority becomes the assigned one."""
    case = case_service.get_case_or_404(db, case_id, current_user)
    updated = case_service.approve_case(db, case, actor=current_user)
    return CaseRead.model_validate(updated)


@router.post("/{case_id}/dismiss", response_model=CaseRead)
def dismiss_case(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_authority_or_admin),
) -> CaseRead:
    """Rejects a case -- either a pending_review submission judged fake/
    invalid, or an already-approved case closed without a resolution (e.g.
    turned out to be a false report). Admins can dismiss any case; an
    authority can dismiss a case that's pending review or already assigned
    to them (see case_service.dismiss_case for the exact rule)."""
    case = case_service.get_case_or_404(db, case_id, current_user)
    updated = case_service.dismiss_case(db, case, actor=current_user)
    return CaseRead.model_validate(updated)


@router.post("/{case_id}/claim", response_model=CaseRead)
def claim_case(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_authority_or_admin),
) -> CaseRead:
    """A verified authority takes ownership of an already-approved,
    unassigned case. FR-3. Restricted to verified authority/admin roles --
    an unverified authority account can't claim cases yet."""
    case = case_service.get_case_or_404(db, case_id, current_user)
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
    level inside case_service.update_case_status. This is how an authority
    closes (resolves) a case once it's solved."""
    case = case_service.get_case_or_404(db, case_id, current_user)
    updated = case_service.update_case_status(db, case, payload.status, actor=current_user)
    return CaseRead.model_validate(updated)


@router.post("/{case_id}/share", status_code=204)
def share_case_route(
    case_id: uuid.UUID,
    payload: CaseShareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_authority_or_admin),
) -> None:
    """Shares this case's full details -- and its photo, as a soft copy --
    with another police/NGO authority by email. That authority can also open
    the case directly on the website via the link in the email. Restricted
    at the row level to the case's assigned authority or an admin (see
    case_service.share_case)."""
    case = case_service.get_case_or_404(db, case_id, current_user)
    case_service.share_case(db, case, payload, actor=current_user)


@router.get("/{case_id}/flyer")
def get_case_flyer(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """A printable one-page PDF flyer for this case -- photo, key details,
    and a QR code linking back to the case page for reporting a sighting.
    Same visibility rule as GET /{case_id} (case_service.get_case_or_404):
    a pending_review or dismissed case is only flyer-able by its reporter or
    an authority/admin, not the general public."""
    case = case_service.get_case_or_404(db, case_id, current_user)
    pdf_bytes = flyer_service.generate_flyer_pdf(case)
    filename = f"missing-{case.name.replace(' ', '-').lower()}-{str(case.id)[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/{case_id}/watch", response_model=WatchStatus)
def get_watch_status(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchStatus:
    """Whether the current user is watching this case -- backs the
    watch/unwatch toggle button on the case detail page."""
    case_service.get_case_or_404(db, case_id, current_user)  # visibility check
    return WatchStatus(is_watching=watch_service.is_watching(db, case_id, current_user.id))


@router.post("/{case_id}/watch", status_code=204)
def watch_case_route(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Subscribes the current user to email updates on this case (status
    changes, verified sightings). Idempotent -- watching an already-watched
    case is a no-op, not an error."""
    case = case_service.get_case_or_404(db, case_id, current_user)
    watch_service.watch_case(db, case, current_user)


@router.delete("/{case_id}/watch", status_code=204)
def unwatch_case_route(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Unsubscribes the current user from this case's email updates.
    Idempotent -- unwatching a case you weren't watching is a no-op."""
    case = case_service.get_case_or_404(db, case_id, current_user)
    watch_service.unwatch_case(db, case, current_user)
