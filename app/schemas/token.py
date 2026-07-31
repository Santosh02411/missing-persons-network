from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import validate_password_byte_length


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str  # user id, as string
    exp: int
    type: str  # "access" | "refresh"


class RefreshRequest(BaseModel):
    refresh_token: str


class EmailVerifyRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
    @field_validator("new_password")
    @classmethod
    def _check_password_byte_length(cls, value: str) -> str:
        return validate_password_byte_length(value)

class LoginResult(BaseModel):
    """Response shape for POST /auth/login. Two possible outcomes in one
    schema (rather than a Union) for simpler OpenAPI docs and frontend
    handling: either tokens are issued directly, or -- if the account has 2FA
    enabled -- mfa_required=True and mfa_token must be paired with a TOTP
    code at POST /auth/2fa/login to actually get tokens."""

    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    mfa_required: bool = False
    mfa_token: str | None = None


class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str


class TwoFactorCodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class TwoFactorLoginRequest(BaseModel):
    mfa_token: str
    code: str = Field(min_length=6, max_length=6)


class SessionRead(BaseModel):
    session_id: str
    created_at: str
    user_agent: str | None = None
