import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.geo import GeoPoint
from app.schemas.user import AuthorityDirectoryItem
from app.services import authority_service
from app.services.geo_service import from_geography, nearby_authorities

router = APIRouter()


def _to_directory_item(user: User, center: GeoPoint | None = None) -> AuthorityDirectoryItem:
    distance_km = None
    if center is not None and user.jurisdiction_location is not None:
        station_point = from_geography(user.jurisdiction_location)
        if station_point is not None:
            # Simple haversine — good enough for a display distance in a
            # picker list; the actual ranking/filtering already happened in
            # the DB via ST_DWithin/ST_Distance.
            lat1, lng1, lat2, lng2 = map(
                math.radians, [center.lat, center.lng, station_point.lat, station_point.lng]
            )
            dlat, dlng = lat2 - lat1, lng2 - lng1
            a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
            distance_km = 2 * 6371 * math.asin(math.sqrt(a))
    return AuthorityDirectoryItem(
        id=user.id,
        full_name=user.full_name,
        org_name=user.org_name,
        email=user.email,
        distance_km=round(distance_km, 1) if distance_km is not None else None,
    )


@router.get("/nearby", response_model=list[AuthorityDirectoryItem])
def get_nearby_authorities(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=100, gt=0, le=500),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AuthorityDirectoryItem]:
    """Backs the "file to this station" picker on the case-creation form --
    verified police/NGO authorities near a given point, nearest first.
    Any logged-in user can call this (a reporter needs it while filing),
    not just authorities."""
    center = GeoPoint(lat=lat, lng=lng)
    authorities = nearby_authorities(db, center, radius_km=radius_km, limit=limit)
    return [_to_directory_item(a, center) for a in authorities]


@router.get("/search", response_model=list[AuthorityDirectoryItem])
def search_authorities(
    q: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AuthorityDirectoryItem]:
    """Backs the "share this case with another authority" picker -- not
    proximity-limited, since sharing deliberately needs to reach stations
    outside the case's own jurisdiction. Any logged-in user can search the
    directory; only the case's assigned authority or an admin can actually
    send a share (enforced in case_service.share_case)."""
    authorities = authority_service.search_authorities(db, q, limit=limit)
    return [_to_directory_item(a) for a in authorities]
