import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import send_email
from app.core.redis_client import redis_client
from app.core.security import hash_password, verify_password
from app.core.totp import generate_totp_secret, get_provisioning_uri, verify_totp_code
from app.models.user import User, UserRole
from app.schemas.user import UserCreate

SESSION_KEY_PREFIX = "refresh_jti"  # kept for backwards-compatible key naming
SESSION_SET_PREFIX = "user_sessions"
LOGIN_FAIL_PREFIX = "login_fail"
LOGIN_LOCK_PREFIX = "login_locked"
EMAIL_VERIFY_PREFIX = "email_verify"
PASSWORD_RESET_PREFIX = "pwd_reset"
PASSWORD_RESET_TTL_SECONDS = 60 * 60  # 1 hour
EMAIL_VERIFY_TTL_SECONDS = 24 * 60 * 60  # 24 hours


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
    """Verifies email+password only. Does NOT check 2FA -- the caller (the
    /auth/login route) decides what to do next based on user.totp_enabled."""
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
# Multi-device sessions
# ---------------------------------------------------------------------------
# Each login/register creates an independent session (a random session_id,
# "sid"), so logging in on a second device does NOT invalidate the first --
# previously this stored a single refresh-token jti per *user*, meaning a
# second login silently kicked out the first device.
#
# Redis layout:
#   refresh_jti:{user_id}:{sid} -> JSON {"jti", "created_at", "user_agent"}
#     (TTL = refresh token lifetime; this is the source of truth for whether
#      a given (sid, jti) pair is still valid)
#   user_sessions:{user_id} -> Redis SET of sid
#     (lets us list/revoke "all of this user's sessions"; entries are
#      cleaned up lazily -- if the individual key has already expired when we
#      look it up, we remove the stale sid from the set at that point)


def create_session_id() -> str:
    return uuid.uuid4().hex


def _session_key(user_id, sid: str) -> str:
    return f"{SESSION_KEY_PREFIX}:{user_id}:{sid}"


def _session_set_key(user_id) -> str:
    return f"{SESSION_SET_PREFIX}:{user_id}"


def store_refresh_jti(user_id, sid: str, jti: str, user_agent: str | None = None) -> None:
    """Records the current valid refresh-token jti for this specific session.
    Called on both login (new session) and refresh (same session, rotated jti)
    -- in both cases this also refreshes the TTL, so an actively-used session
    doesn't expire out from under someone mid-use."""
    value = json.dumps(
        {
            "jti": jti,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "user_agent": user_agent,
        }
    )
    redis_client.set(
        _session_key(user_id, sid), value, ex=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )
    redis_client.sadd(_session_set_key(user_id), sid)


def is_refresh_jti_valid(user_id, sid: str, jti: str) -> bool:
    stored = redis_client.get(_session_key(user_id, sid))
    if stored is None:
        return False
    try:
        return json.loads(stored)["jti"] == jti
    except (json.JSONDecodeError, KeyError):
        return False


def revoke_session(user_id, sid: str) -> None:
    """Used by logout (single device) and internally when a stale/reused
    refresh token is presented for that session."""
    redis_client.delete(_session_key(user_id, sid))
    redis_client.srem(_session_set_key(user_id), sid)


def revoke_all_sessions(user_id) -> None:
    """Used by 'log out everywhere', password reset, and admin account
    deactivation -- every device is signed out, not just the current one."""
    sids = redis_client.smembers(_session_set_key(user_id))
    for sid in sids:
        redis_client.delete(_session_key(user_id, sid))
    redis_client.delete(_session_set_key(user_id))


def list_sessions(user_id) -> list[dict]:
    """Backs GET /auth/sessions ("your devices"). Lazily drops any sid whose
    individual key has already expired, instead of leaving stale entries in
    the set forever."""
    sids = redis_client.smembers(_session_set_key(user_id))
    sessions = []
    for sid in sids:
        raw = redis_client.get(_session_key(user_id, sid))
        if raw is None:
            redis_client.srem(_session_set_key(user_id), sid)
            continue
        data = json.loads(raw)
        sessions.append(
            {
                "session_id": sid,
                "created_at": data.get("created_at"),
                "user_agent": data.get("user_agent"),
            }
        )
    return sorted(sessions, key=lambda s: s["created_at"], reverse=True)


# Backwards-compatible alias -- older call sites (password reset, admin
# deactivation) conceptually want "kill this user's session(s)"; multi-device
# support means that's now "all sessions" rather than a single one.
def revoke_refresh_token(user_id) -> None:
    revoke_all_sessions(user_id)


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

    # Resetting the password invalidates every existing session -- if someone
    # else had access to the old password/a refresh token, this cuts them off
    # on every device, not just the one making the reset request.
    revoke_all_sessions(user.id)
    return user


# ---------------------------------------------------------------------------
# Two-factor auth (TOTP)
# ---------------------------------------------------------------------------


def start_totp_setup(db: Session, user: User) -> tuple[str, str]:
    """Generates a new secret and stores it un-confirmed (totp_enabled stays
    False until confirm_totp_setup succeeds). Calling this again before
    confirming just overwrites the pending secret -- lets someone restart if
    they didn't finish scanning the QR code in time."""
    if user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Two-factor authentication is already enabled. Disable it first to set up a new authenticator.",
        )
    secret = generate_totp_secret()
    user.totp_secret = secret
    db.commit()
    return secret, get_provisioning_uri(secret, user.email)


def confirm_totp_setup(db: Session, user: User, code: str) -> User:
    if not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No two-factor setup in progress. Call /auth/2fa/setup first.",
        )
    if not verify_totp_code(user.totp_secret, code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect code. Check your authenticator app and try again.",
        )
    user.totp_enabled = True
    db.commit()
    db.refresh(user)
    return user


def disable_totp(db: Session, user: User, code: str) -> User:
    if not user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is not enabled on this account.",
        )
    if not verify_totp_code(user.totp_secret, code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect code.")
    user.totp_enabled = False
    user.totp_secret = None
    db.commit()
    db.refresh(user)
    return user
