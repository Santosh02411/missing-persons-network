from pydantic import BaseModel, Field


class GeoPoint(BaseModel):
    """Plain lat/lng for API input/output. Converted to/from PostGIS
    geography(Point, 4326) in the service layer — the API never deals with WKB directly."""

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
