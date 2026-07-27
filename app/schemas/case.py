import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

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


class CaseListItem(BaseModel):
    """Slimmer shape for list views — avoids shipping the full description to a browse page."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    photo_url: str | None
    last_seen_address: str
    status: CaseStatus
    created_at: datetime
