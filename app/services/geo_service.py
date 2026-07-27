from geoalchemy2.elements import WKBElement, WKTElement
from geoalchemy2.shape import to_shape

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


# NOTE (Phase 4): nearby_sightings() / nearby_cases() using ST_DWithin +
# distance ordering land here, backed by the GiST spatial index added in that
# phase's migration. See docs/TECHNICAL_ARCHITECTURE.md for the query shape.
