import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.sighting import SightingStatus
from app.schemas.geo import GeoPoint


class SightingCreate(BaseModel):
    case_id: uuid.UUID
    location: GeoPoint
    address_text: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1)
    photo_url: str | None = Field(default=None, max_length=500)


class SightingReview(BaseModel):
    status: SightingStatus = Field(
        description="Must be 'verified' or 'dismissed' — 'pending' is not a valid review outcome."
    )


class SightingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    reported_by: uuid.UUID | None
    location: GeoPoint
    address_text: str
    description: str
    photo_url: str | None
    status: SightingStatus
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    created_at: datetime


class SightingQueueItem(SightingRead):
    """SightingRead plus the parent case's name -- used only by the pending-
    review queue endpoint, so the authority dashboard doesn't need a second
    request per row just to show which case a sighting belongs to."""

    case_name: str
