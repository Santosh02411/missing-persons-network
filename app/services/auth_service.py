import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import send_email
from app.core.redis_client import redis_client
from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate

REFRESH_KEY_PREFIX = "refresh_jti"
LOGIN_FAIL_PREFIX = "login_fail"
LOGIN_LOCK_PREFIX = "login_locked"
EMAIL_VERIFY_PREFIX = "email_verify"
PASSWORD_RESET_PREFIX = "pwd_reset"
PASSWORD_RESET_TTL_SECONDS = 60 * 60  # 1 hour
EMAIL_VERIFY_TTL_SECONDS = 24 * 60 * 60  # 24 hours


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
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    send_verification_email(user)
    return user


# ---------------------------------------------------------------------------
# Login lockout
# ---------------------------------------------------------------------------
# Fixed-window failure counter + a separate lock flag, both in Redis and both
# keyed by email (not user id -- we need to track failures even for emails
# that don't exist, without leaking whether the account exists via timing or
# a different error message).


def _login_fail_key(email: str) -> str:
    return f"{LOGIN_FAIL_PREFIX}:{email}"


def _login_lock_key(email: str) -> str:
    return f"{LOGIN_LOCK_PREFIX}:{email}"


def _check_not_locked(email: str) -> None:
    ttl = redis_client.ttl(_login_lock_key(email))
    if ttl and ttl > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please wait before trying again.",
            headers={"Retry-After": str(ttl)},
        )


def _record_login_failure(email: str) -> None:
    key = _login_fail_key(email)
    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, settings.LOGIN_FAILURE_WINDOW_SECONDS)
    if count >= settings.LOGIN_FAILURE_THRESHOLD:
        redis_client.set(_login_lock_key(email), "1", ex=settings.LOGIN_LOCKOUT_SECONDS)


def _clear_login_failures(email: str) -> None:
    redis_client.delete(_login_fail_key(email))
    redis_client.delete(_login_lock_key(email))


def authenticate_user(db: Session, email: str, password: str) -> User:
    _check_not_locked(email)

    user = get_user_by_email(db, email)
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
    )
    if user is None or not verify_password(password, user.hashed_password):
        _record_login_failure(email)
        raise invalid_credentials
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated"
        )

    _clear_login_failures(email)
    return user


# ---------------------------------------------------------------------------
# Refresh token rotation (Phase 3)
# ---------------------------------------------------------------------------


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
    """Used by logout, password reset, and internally when a stale/reused
    refresh token is presented — treat that as a signal to kill the whole
    refresh session."""
    redis_client.delete(_refresh_key(user_id))


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


def send_verification_email(user: User) -> None:
    token = uuid.uuid4().hex
    redis_client.set(f"{EMAIL_VERIFY_PREFIX}:{token}", str(user.id), ex=EMAIL_VERIFY_TTL_SECONDS)
    verify_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    send_email(
        to=user.email,
        subject="Confirm your email — Reunification Network",
        body=(
            f"Hi {user.full_name},\n\n"
            f"Please confirm your email address by opening this link:\n{verify_link}\n\n"
            f"This link expires in 24 hours."
        ),
    )


def verify_email_token(db: Session, token: str) -> User:
    key = f"{EMAIL_VERIFY_PREFIX}:{token}"
    user_id = redis_client.get(key)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification link is invalid or has expired.",
        )
    redis_client.delete(key)

    user = db.get(User, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.email_verified = True
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


def request_password_reset(db: Session, email: str) -> None:
    """Always succeeds from the caller's point of view (no indication of
    whether the email exists) -- this prevents using the forgot-password
    endpoint to enumerate registered accounts. The actual email is only sent
    if the account exists."""
    user = get_user_by_email(db, email)
    if user is None:
        return

    token = uuid.uuid4().hex
    redis_client.set(
        f"{PASSWORD_RESET_PREFIX}:{token}", str(user.id), ex=PASSWORD_RESET_TTL_SECONDS
    )
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    send_email(
        to=user.email,
        subject="Reset your password — Reunification Network",
        body=(
            f"Hi {user.full_name},\n\n"
            f"Someone requested a password reset for this account. If this was you, "
            f"open this link to choose a new password:\n{reset_link}\n\n"
            f"This link expires in 1 hour. If you didn't request this, you can ignore this email."
        ),
    )


def reset_password(db: Session, token: str, new_password: str) -> User:
    key = f"{PASSWORD_RESET_PREFIX}:{token}"
    user_id = redis_client.get(key)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link is invalid or has expired.",
        )
    redis_client.delete(key)

    user = db.get(User, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.hashed_password = hash_password(new_password)
    db.commit()
    db.refresh(user)

    # Resetting the password invalidates any existing session -- if someone
    # else had access to the old password/refresh token, this cuts them off.
    revoke_refresh_token(user.id)
    return user
