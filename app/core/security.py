import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(subject: uuid.UUID, expires_delta: timedelta, token_type: Literal["access", "refresh"]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "exp": now + expires_delta,
        "iat": now,
        "type": token_type,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: uuid.UUID) -> str:
    return _create_token(
        user_id, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), "access"
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    return _create_token(
        user_id, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), "refresh"
    )


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
