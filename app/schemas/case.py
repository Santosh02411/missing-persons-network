import uuid
from datetime import datetime

<<<<<<< HEAD
from pydantic import BaseModel, ConfigDict, Field, field_validator
=======
from pydantic import BaseModel, ConfigDict, Field
>>>>>>> 0a84c8b8037ce65b90f512ff6a732d74ee3d7e30

from app.models.case import CaseStatus
from app.schemas.geo import GeoPoint


class CaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    age_at_disappearance: int | None = Field(default=None, ge=0, le=130)
    photo_url: str | None = Field(default=None, max_length=500)
    description: str = Field(min_length=1)
    last_seen_location: GeoPoint
    last_seen_address: str = Field(min_length=1, max_length=500)
    last_seen_at: datetime


class CaseUpdate(BaseModel):
    """Partial update — all fields optional. Status is intentionally excluded;
    that goes through the dedicated status-change endpoint so it can carry its
    own audit-log write and (Phase 3) role gate."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    photo_url: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, min_length=1)
    last_seen_location: GeoPoint | None = None
    last_seen_address: str | None = Field(default=None, min_length=1, max_length=500)


class CaseStatusUpdate(BaseModel):
    status: CaseStatus


class CaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_by: uuid.UUID
    name: str
    age_at_disappearance: int | None
    photo_url: str | None
    description: str
    last_seen_location: GeoPoint
    last_seen_address: str
    last_seen_at: datetime
    status: CaseStatus
    assigned_authority_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

<<<<<<< HEAD
    @field_validator("last_seen_location", mode="before")
    @classmethod
    def _convert_geography(cls, value):
        # Reading a Case back from the DB gives a raw geoalchemy2 WKBElement
        # for this column, not a {lat, lng} shape -- this was previously
        # missing entirely (geo_service.from_geography() existed but was
        # never actually called from here), so every case-detail fetch
        # crashed with a Pydantic validation error the moment it tried to
        # build a GeoPoint straight from a WKBElement's attributes.
        from app.services.geo_service import from_geography

        if isinstance(value, dict):
            return value  # already {lat, lng} -- e.g. round-tripped in tests
        return from_geography(value)

=======
>>>>>>> 0a84c8b8037ce65b90f512ff6a732d74ee3d7e30

class CaseListItem(BaseModel):
    """Slimmer shape for list views — avoids shipping the full description to a browse page."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    photo_url: str | None
    last_seen_address: str
    status: CaseStatus
    created_at: datetime
