import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.case import BLOOD_TYPES, CaseStatus
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

    # Structured physical identifiers -- all optional at filing time, since
    # most reporters won't know or think to include all of these under
    # pressure, and none of them should block filing a case.
    height_cm: int | None = Field(default=None, ge=0, le=300)
    eye_color: str | None = Field(default=None, max_length=30)
    hair_color: str | None = Field(default=None, max_length=30)
    blood_type: str | None = Field(default=None, max_length=10)
    distinguishing_marks: str | None = Field(default=None, max_length=2000)
    medical_conditions: str | None = Field(default=None, max_length=2000)

    @field_validator("blood_type")
    @classmethod
    def _validate_blood_type(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in BLOOD_TYPES:
            raise ValueError(f"blood_type must be one of {', '.join(BLOOD_TYPES)}")
        return value

    # Optional: the reporter can pick a specific police station / NGO to
    # file this case with (from the nearby-authorities picker). If omitted,
    # case_service.create_case auto-routes to the nearest verified station
    # instead of broadcasting the case to every authority nationwide.
    target_authority_id: uuid.UUID | None = None


class CaseUpdate(BaseModel):
    """Partial update — all fields optional. Status is intentionally excluded;
    that goes through the dedicated status-change endpoint so it can carry its
    own audit-log write and (Phase 3) role gate. Age-progression fields are
    also excluded here -- they go through the dedicated
    PATCH /{case_id}/age-progression endpoint instead, which is restricted
    to whoever has case access rather than following this endpoint's
    owner-or-authority rule (see case_service.update_case)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    age_at_disappearance: int | None = Field(default=None, ge=0, le=130)
    gender: str | None = Field(default=None, max_length=30)
    photo_url: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, min_length=1)
    last_seen_location: GeoPoint | None = None
    last_seen_address: str | None = Field(default=None, min_length=1, max_length=500)
    height_cm: int | None = Field(default=None, ge=0, le=300)
    eye_color: str | None = Field(default=None, max_length=30)
    hair_color: str | None = Field(default=None, max_length=30)
    blood_type: str | None = Field(default=None, max_length=10)
    distinguishing_marks: str | None = Field(default=None, max_length=2000)
    medical_conditions: str | None = Field(default=None, max_length=2000)

    @field_validator("blood_type")
    @classmethod
    def _validate_blood_type_update(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in BLOOD_TYPES:
            raise ValueError(f"blood_type must be one of {', '.join(BLOOD_TYPES)}")
        return value


class AgeProgressionUpdate(BaseModel):
    age_progressed_photo_url: str = Field(min_length=1, max_length=500)
    age_progression_note: str | None = Field(default=None, max_length=2000)


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
    possible_duplicates: list[dict] = []
    age_progressed_photo_url: str | None = None
    age_progression_note: str | None = None
    height_cm: int | None = None
    eye_color: str | None = None
    hair_color: str | None = None
    blood_type: str | None = None
    distinguishing_marks: str | None = None
    medical_conditions: str | None = None
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


class DuplicateCheckRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    age_at_disappearance: int | None = Field(default=None, ge=0, le=130)
    last_seen_location: GeoPoint
    last_seen_at: datetime


class DuplicateMatch(BaseModel):
    case_id: uuid.UUID
    name: str
    status: CaseStatus
    similarity: float
    distance_km: float | None


class RegistrySyncReceipt(BaseModel):
    case_id: uuid.UUID
    submitted_at: datetime
    note: str


class TimelineEvent(BaseModel):
    timestamp: datetime
    type: str
    label: str


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
    last_seen_location: GeoPoint
    status: CaseStatus
    created_at: datetime

    @field_validator("last_seen_location", mode="before")
    @classmethod
    def _convert_geography_list_item(cls, value):
        from app.services.geo_service import from_geography

        if isinstance(value, dict):
            return value
        return from_geography(value)
