import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    photo_match_score: float | None
    status: SightingStatus
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    created_at: datetime

    @field_validator("location", mode="before")
    @classmethod
    def _convert_geography(cls, value):
        # Same issue as CaseRead.last_seen_location -- see that validator's
        # comment for the full explanation. A raw WKBElement from the DB
        # needs explicit conversion; it was never wired up before.
        from app.services.geo_service import from_geography

        if isinstance(value, dict):
            return value
        return from_geography(value)


class ReporterStats(BaseModel):
    verified: int
    dismissed: int
    pending: int
    total: int


class SightingQueueItem(SightingRead):
    """SightingRead plus the parent case's name -- used only by the pending-
    review queue endpoint, so the authority dashboard doesn't need a second
    request per row just to show which case a sighting belongs to."""

    case_name: str
    # The reporting user's sighting-accuracy history -- authority-facing
    # only (this schema is never returned to a reporter or the public).
    # None for anonymous/reporter-less sightings, which have no history to show.
    reporter_stats: ReporterStats | None = None
