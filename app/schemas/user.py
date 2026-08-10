import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import validate_password_byte_length
from app.models.user import UserRole
from app.schemas.geo import GeoPoint


class UserCreate(BaseModel):
    """Registration payload. `role` defaults to reporter — becoming an
    authority requires requesting that role explicitly and then admin approval.

    `role` is deliberately typed as a Literal of only "reporter"/"authority" --
    NOT the full UserRole enum. Admin accounts must never be self-registerable
    through this public endpoint; there is currently no verification gate on
    the admin role itself (unlike authority, which has is_verified), so
    accepting role="admin" here would let anyone grant themselves full admin
    access. Admin accounts are created out-of-band (e.g. directly in the
    database, or a future internal-only endpoint) -- not via this schema.
    """

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    role: Literal["reporter", "authority"] = "reporter"
    org_name: str | None = Field(default=None, max_length=255)

    # Only meaningful when role="authority" -- the station/office location,
    # used to route newly-filed cases to the nearest station instead of
    # broadcasting every case nationwide. Optional at signup; an authority
    # can also set this later (see PATCH /auth/me/jurisdiction).
    jurisdiction_location: GeoPoint | None = None

    @field_validator("password")
    @classmethod
    def _check_password_byte_length(cls, value: str) -> str:
        # bcrypt (used for hashing, see core/security.py) hard-caps at 72
        # BYTES, not characters -- a password with accented/non-Latin
        # characters can hit that limit well under 72 characters. Without
        # this check, a too-long password passes max_length=128 here but
        # then crashes hash_password() with an unhandled 500 at registration.
        return validate_password_byte_length(value)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_verified: bool
    is_active: bool
    email_verified: bool
    totp_enabled: bool
    email_otp_enabled: bool
    sms_otp_enabled: bool
    phone_number: str | None = None
    org_name: str | None = None
    jurisdiction_location: GeoPoint | None = None

    @field_validator("jurisdiction_location", mode="before")
    @classmethod
    def _convert_jurisdiction_geography(cls, value):
        # Same WKBElement -> GeoPoint conversion CaseRead needs -- reading a
        # User back from the DB gives a raw geoalchemy2 WKBElement for this
        # column, not a {lat, lng} shape.
        from app.services.geo_service import from_geography

        if value is None or isinstance(value, dict):
            return value
        return from_geography(value)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class JurisdictionUpdate(BaseModel):
    """Lets an authority account set or update its station location after
    signup, without needing a full profile-edit endpoint."""

    jurisdiction_location: GeoPoint


class AuthorityDirectoryItem(BaseModel):
    """Slim shape for the "file to this station" / "share with this
    authority" pickers -- deliberately not the full UserRead."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    org_name: str | None
    email: EmailStr
    distance_km: float | None = None
