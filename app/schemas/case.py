import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.case import CaseStatus
from app.schemas.geo import GeoPoint


class CaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    age_at_disappearance: int | None = Field(default=None, ge=0, le=130)
    gender: str | None = Field(default=None, max_length=30)
    photo_url: str | None = Field(default=None, max_length=500)
    description: str = Field(min_length=1)
    last_seen_location: GeoPoint
    last_seen_address: str = Field(min_length=1, max_length=500)
    last_seen_at: datetime

    # Optional: the reporter can pick a specific police station / NGO to
    # file this case with (from the nearby-authorities picker). If omitted,
    # case_service.create_case auto-routes to the nearest verified station
    # instead of broadcasting the case to every authority nationwide.
    target_authority_id: uuid.UUID | None = None


class CaseUpdate(BaseModel):
    """Partial update — all fields optional. Status is intentionally excluded;
    that goes through the dedicated status-change endpoint so it can carry its
    own audit-log write and (Phase 3) role gate."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    age_at_disappearance: int | None = Field(default=None, ge=0, le=130)
    gender: str | None = Field(default=None, max_length=30)
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
    gender: str | None
    photo_url: str | None
    description: str
    last_seen_location: GeoPoint
    last_seen_address: str
    last_seen_at: datetime
    status: CaseStatus
    assigned_authority_id: uuid.UUID | None
    target_authority_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

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


class CaseShareRequest(BaseModel):
    """Exactly one of to_authority_id (an existing authority account) or
    to_email (any address -- e.g. a station not yet registered on the
    platform) must be set."""

    to_authority_id: uuid.UUID | None = None
    to_email: str | None = Field(default=None, max_length=255)
    message: str | None = Field(default=None, max_length=1000)

    @field_validator("to_email")
    @classmethod
    def _validate_email_shape(cls, value: str | None) -> str | None:
        if value is None:
            return value
        # Lightweight shape check -- full EmailStr validation would reject
        # this field being absent/None, which is fine here since exactly one
        # of the two target fields is required (checked in the route).
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Enter a valid email address")
        return value


class CaseListItem(BaseModel):
    """Slimmer shape for list views — avoids shipping the full description to a browse page."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    age_at_disappearance: int | None
    gender: str | None
    photo_url: str | None
    last_seen_address: str
    last_seen_at: datetime
    status: CaseStatus
    created_at: datetime
