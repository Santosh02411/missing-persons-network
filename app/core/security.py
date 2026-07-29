import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal, TypedDict

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


class RefreshTokenData(TypedDict):
    user_id: uuid.UUID
    jti: str


def _create_token(
    subject: uuid.UUID,
    expires_delta: timedelta,
    token_type: Literal["access", "refresh"],
    jti: str | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "exp": now + expires_delta,
        "iat": now,
        "type": token_type,
    }
    if jti is not None:
        payload["jti"] = jti
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: uuid.UUID) -> str:
    return _create_token(
        user_id, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), "access"
    )


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, str]:
    """Returns (token, jti). The jti is stored server-side (Redis) so a
    refresh token can be individually revoked/rotated — a bare JWT can't be
    invalidated before it expires on its own otherwise."""
    jti = str(uuid.uuid4())
    token = _create_token(
        user_id, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), "refresh", jti=jti
    )
    return token, jti


class InvalidTokenError(Exception):
    pass


def decode_token(token: str, expected_type: Literal["access", "refresh"]) -> uuid.UUID:
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
    """Like decode_token, but also extracts the jti — needed by auth_service
    to check the token against what's stored in Redis (rotation/revocation)."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise InvalidTokenError("Could not validate token") from exc

    if payload.get("type") != "refresh":
        raise InvalidTokenError("Expected a refresh token")

    sub = payload.get("sub")
    jti = payload.get("jti")
    if sub is None or jti is None:
        raise InvalidTokenError("Refresh token missing subject or jti")

    try:
        user_id = uuid.UUID(sub)
    except ValueError as exc:
        raise InvalidTokenError("Token subject is not a valid user id") from exc

    return RefreshTokenData(user_id=user_id, jti=jti)
