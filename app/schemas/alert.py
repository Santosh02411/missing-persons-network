from pydantic import BaseModel, Field

from app.schemas.geo import GeoPoint


class AlertPreferencesUpdate(BaseModel):
    enabled: bool
    location: GeoPoint | None = None
    radius_km: float | None = Field(default=None, gt=0, le=500)


class AlertSendResult(BaseModel):
    notified_count: int
