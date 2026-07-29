import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


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


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_verified: bool
    is_active: bool
    email_verified: bool
    org_name: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str
