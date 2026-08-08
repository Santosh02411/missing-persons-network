from geoalchemy2.elements import WKBElement, WKTElement
from geoalchemy2.shape import to_shape
from geoalchemy2.types import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.models.case import Case, CaseStatus
from app.models.sighting import Sighting
from app.models.user import User, UserRole
from app.schemas.geo import GeoPoint

SRID = 4326


def to_geography(point: GeoPoint) -> WKTElement:
    """Convert an API-level GeoPoint into a PostGIS-ready WKT element for storage."""
    return WKTElement(f"POINT({point.lng} {point.lat})", srid=SRID)


def from_geography(value: WKBElement | None) -> GeoPoint | None:
    """Convert a PostGIS geography column value back into a plain GeoPoint for API responses."""
    if value is None:
        return None
    shapely_point = to_shape(value)
    return GeoPoint(lat=shapely_point.y, lng=shapely_point.x)


def _geography_point(point: GeoPoint):
    """Build a geography-typed point literal for use in ST_DWithin/ST_Distance.
    Explicitly cast to Geography so distances come out in meters and the
    GiST spatial index (see alembic/versions/0002_geo_indexes.py) can be used."""
    return cast(func.ST_SetSRID(func.ST_MakePoint(point.lng, point.lat), SRID), Geography)


def nearby_sightings(
    db: Session, center: GeoPoint, radius_km: float, limit: int = 50
) -> list[Sighting]:
    """FR-10: sightings within `radius_km` of `center`, nearest first."""
    point = _geography_point(center)
    radius_m = radius_km * 1000
    stmt = (
        select(Sighting)
        .where(func.ST_DWithin(Sighting.location, point, radius_m))
        .order_by(func.ST_Distance(Sighting.location, point))
        .limit(limit)
    )
    return list(db.scalars(stmt))


def nearby_cases(
    db: Session, center: GeoPoint, radius_km: float, limit: int = 50
) -> list[Case]:
    """FR-11: open cases whose last-seen location is within `radius_km` of
    `center`, nearest first. Restricted to OPEN cases — a resolved or
    lead-found case showing up in a "nearby missing persons" search isn't
    useful to the person searching."""
    point = _geography_point(center)
    radius_m = radius_km * 1000
    stmt = (
        select(Case)
        .where(
            func.ST_DWithin(Case.last_seen_location, point, radius_m),
            Case.status == CaseStatus.OPEN,
        )
        .order_by(func.ST_Distance(Case.last_seen_location, point))
        .limit(limit)
    )
    return list(db.scalars(stmt))


def nearby_authorities(
    db: Session, center: GeoPoint, radius_km: float = 100, limit: int = 20
) -> list[User]:
    """Verified authority/NGO accounts whose station (jurisdiction_location)
    is within `radius_km` of `center`, nearest first. Backs both the "file
    to this station" picker on case creation and the nearest-station
    auto-routing fallback in case_service.create_case. Authorities that
    haven't set a jurisdiction_location are never returned here (there's
    nothing to measure distance to) -- see list_all_authorities() below for
    those."""
    point = _geography_point(center)
    radius_m = radius_km * 1000
    stmt = (
        select(User)
        .where(
            User.role == UserRole.AUTHORITY,
            User.is_verified.is_(True),
            User.is_active.is_(True),
            User.jurisdiction_location.isnot(None),
            func.ST_DWithin(User.jurisdiction_location, point, radius_m),
        )
        .order_by(func.ST_Distance(User.jurisdiction_location, point))
        .limit(limit)
    )
    return list(db.scalars(stmt))


def nearest_authority(db: Session, center: GeoPoint, radius_km: float = 100) -> User | None:
    """Single nearest verified station within `radius_km`, or None if no
    station has a jurisdiction set within range -- the caller (case_service)
    treats None as "fall back to broadcasting this case to any authority"
    rather than as an error."""
    matches = nearby_authorities(db, center, radius_km=radius_km, limit=1)
    return matches[0] if matches else None
