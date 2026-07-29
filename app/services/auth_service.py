from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.redis_client import redis_client
from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate

REFRESH_KEY_PREFIX = "refresh_jti"


def _refresh_key(user_id) -> str:
    return f"{REFRESH_KEY_PREFIX}:{user_id}"


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def register_user(db: Session, payload: UserCreate) -> User:
    if get_user_by_email(db, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # Authority accounts start unverified regardless of what's requested at
    # signup — an admin must approve them (see docs/SECURITY_AND_ACCESS.md).
    # payload.role is a Literal["reporter", "authority"] (see schemas/user.py
    # for why admin can never come through here), so this UserRole(...)
    # conversion can only ever produce REPORTER or AUTHORITY.
    role = UserRole(payload.role)
    is_verified = role == UserRole.REPORTER

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=role,
        org_name=payload.org_name if role == UserRole.AUTHORITY else None,
        is_verified=is_verified,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
    )
    if user is None or not verify_password(password, user.hashed_password):
        raise invalid_credentials
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated"
        )
    return user


def store_refresh_jti(user_id, jti: str) -> None:
    """Record the *current* valid refresh token's jti for this user in Redis,
    with a TTL matching the token's own expiry. Overwrites any previous jti —
    logging in again (or refreshing) invalidates the prior refresh token,
    since only the latest jti is considered valid."""
    redis_client.set(
        _refresh_key(user_id),
        jti,
        ex=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )


def is_refresh_jti_valid(user_id, jti: str) -> bool:
    stored = redis_client.get(_refresh_key(user_id))
    return stored is not None and stored == jti


def revoke_refresh_token(user_id) -> None:
    """Used by logout, and internally when a stale/reused refresh token is
    presented — treat that as a signal to kill the whole refresh session."""
    redis_client.delete(_refresh_key(user_id))
