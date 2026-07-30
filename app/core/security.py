import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal, TypedDict

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

MFA_TOKEN_EXPIRE_MINUTES = 5


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


class RefreshTokenData(TypedDict):
    user_id: uuid.UUID
    jti: str
    sid: str


def _create_token(
    subject: uuid.UUID,
    expires_delta: timedelta,
    token_type: Literal["access", "refresh", "mfa"],
    extra_claims: dict | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "exp": now + expires_delta,
        "iat": now,
        "type": token_type,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: uuid.UUID, sid: str) -> str:
    """`sid` (session id) is embedded so /auth/logout can identify which
    session to revoke without the client having to resend its refresh token —
    see core/deps.py's get_current_session_id."""
    return _create_token(
        user_id,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "access",
        extra_claims={"sid": sid},
    )


def create_refresh_token(user_id: uuid.UUID, sid: str) -> tuple[str, str]:
    """Returns (token, jti). `sid` identifies the session/device this token
    belongs to and stays constant across refresh-token rotation for that
    session (see auth_service's multi-device session storage); `jti`
    identifies this specific token issuance and changes every rotation."""
    jti = str(uuid.uuid4())
    token = _create_token(
        user_id,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "refresh",
        extra_claims={"jti": jti, "sid": sid},
    )
    return token, jti


def create_mfa_token(user_id: uuid.UUID) -> str:
    """Short-lived token proving "this request already passed the password
    check" -- issued after a correct password when 2FA is enabled, and
    required (alongside a valid TOTP code) to complete login via
    /auth/2fa/login. Deliberately short-lived (5 min) and a distinct token
    `type` so it can't be mistaken for or reused as an access/refresh token."""
    return _create_token(user_id, timedelta(minutes=MFA_TOKEN_EXPIRE_MINUTES), "mfa")


class InvalidTokenError(Exception):
    pass


def decode_token(token: str, expected_type: Literal["access", "refresh", "mfa"]) -> uuid.UUID:
    """Decode and validate a JWT, returning the user id encoded in `sub`.
    Raises InvalidTokenError on any failure — expired, malformed, or wrong type."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise InvalidTokenError("Could not validate token") from exc

    if payload.get("type") != expected_type:
        raise InvalidTokenError(f"Expected a {expected_type} token")

    sub = payload.get("sub")
    if sub is None:
        raise InvalidTokenError("Token missing subject")

    try:
        return uuid.UUID(sub)
    except ValueError as exc:
        raise InvalidTokenError("Token subject is not a valid user id") from exc


def decode_refresh_token(token: str) -> RefreshTokenData:
    """Like decode_token, but also extracts jti and sid — needed by
    auth_service to check the token against what's stored in Redis for that
    specific session (rotation/revocation)."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise InvalidTokenError("Could not validate token") from exc

    if payload.get("type") != "refresh":
        raise InvalidTokenError("Expected a refresh token")

    sub = payload.get("sub")
    jti = payload.get("jti")
    sid = payload.get("sid")
    if sub is None or jti is None or sid is None:
        raise InvalidTokenError("Refresh token missing subject, jti, or sid")

    try:
        user_id = uuid.UUID(sub)
    except ValueError as exc:
        raise InvalidTokenError("Token subject is not a valid user id") from exc

    return RefreshTokenData(user_id=user_id, jti=jti, sid=sid)


def decode_access_token_sid(token: str) -> str:
    """Extracts just the sid claim from an access token -- used only by
    /auth/logout (via get_current_session_id) to know which session to
    revoke. Kept separate from get_current_user so that dependency's
    signature/return type didn't need to change everywhere it's already used."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise InvalidTokenError("Could not validate token") from exc

    if payload.get("type") != "access":
        raise InvalidTokenError("Expected an access token")

    sid = payload.get("sid")
    if sid is None:
        raise InvalidTokenError("Token missing sid")
    return sid
