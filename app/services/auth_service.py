import json
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import send_email
from app.core.sms import send_sms
from app.core.redis_client import redis_client
from app.core.security import hash_password, verify_password
from app.core.totp import generate_totp_secret, get_provisioning_uri, verify_totp_code
from app.models.user import User, UserRole
from app.schemas.geo import GeoPoint
from app.schemas.user import UserCreate

SESSION_KEY_PREFIX = "refresh_jti"  # kept for backwards-compatible key naming
SESSION_SET_PREFIX = "user_sessions"
LOGIN_FAIL_PREFIX = "login_fail"
LOGIN_LOCK_PREFIX = "login_locked"
EMAIL_VERIFY_PREFIX = "email_verify"
PASSWORD_RESET_PREFIX = "pwd_reset"
PASSWORD_RESET_TTL_SECONDS = 60 * 60  # 1 hour
EMAIL_VERIFY_TTL_SECONDS = 24 * 60 * 60  # 24 hours
LOGIN_OTP_PREFIX = "login_otp"  # a fresh code sent at each email-OTP login
LOGIN_OTP_TTL_SECONDS = 5 * 60
SETUP_OTP_PREFIX = "email_otp_setup"  # confirms the person can receive email before enabling
SETUP_OTP_TTL_SECONDS = 10 * 60
RESEND_COOLDOWN_PREFIX = "login_otp_resend_cooldown"


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
    if role == UserRole.AUTHORITY and payload.jurisdiction_location is not None:
        from app.services.geo_service import to_geography

        user.jurisdiction_location = to_geography(payload.jurisdiction_location)
    db.add(user)
    db.commit()
    db.refresh(user)

    send_verification_email(user)
    return user


def update_jurisdiction(db: Session, user: User, location: GeoPoint) -> User:
    """Lets an authority set/update its station location after signup (e.g.
    it wasn't provided at registration). Route-level require_role already
    restricts this to authority/admin accounts; case_service's nearest-
    station routing simply won't match this account until it's set."""
    from app.services.geo_service import to_geography

    user.jurisdiction_location = to_geography(location)
    db.commit()
    db.refresh(user)
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
    if user.email_otp_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have email-based 2FA enabled. Disable it first to switch methods.",
        )
    if user.sms_otp_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have SMS-based 2FA enabled. Disable it first to switch methods.",
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


# ---------------------------------------------------------------------------
# Two-factor auth: email OTP (alternative to TOTP)
# ---------------------------------------------------------------------------
# No secret is stored on the user for this method -- each code is randomly
# generated, emailed, and checked against a short-lived Redis entry, both
# when setting the method up and at every subsequent login.


def _generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def start_email_otp_setup(db: Session, user: User) -> None:
    """Sends a confirmation code to the account's email -- proves the person
    setting this up can actually receive mail there before enabling it."""
    if user.email_otp_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email OTP is already enabled. Disable it first to reconfigure.",
        )
    if user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have authenticator-app 2FA enabled. Disable it first to switch methods.",
        )
    if user.sms_otp_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have SMS-based 2FA enabled. Disable it first to switch methods.",
        )
    code = _generate_otp_code()
    redis_client.set(f"{SETUP_OTP_PREFIX}:{user.id}", code, ex=SETUP_OTP_TTL_SECONDS)
    send_email(
        to=user.email,
        subject="Confirm email-based two-factor auth — Reunification Network",
        body=(
            f"Hi {user.full_name},\n\nYour confirmation code is: {code}\n\n"
            f"Enter this on the site to finish enabling email-based two-factor "
            f"authentication. This code expires in 10 minutes."
        ),
    )


def confirm_email_otp_setup(db: Session, user: User, code: str) -> User:
    key = f"{SETUP_OTP_PREFIX}:{user.id}"
    stored = redis_client.get(key)
    if stored is None or stored != code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect or expired code. Request a new one and try again.",
        )
    redis_client.delete(key)
    user.email_otp_enabled = True
    db.commit()
    db.refresh(user)
    return user


def disable_email_otp(db: Session, user: User) -> User:
    """No code challenge required to disable -- unlike TOTP disable, there's
    no standing secret to prove possession of; the person is already
    authenticated with a valid access token, which is enough here."""
    if not user.email_otp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email OTP is not enabled on this account.",
        )
    user.email_otp_enabled = False
    db.commit()
    db.refresh(user)
    return user


def send_login_otp(user: User) -> None:
    """Called from the /auth/login route when a user with email_otp_enabled
    passes the password check -- sends the code they'll need for
    /auth/2fa/login."""
    code = _generate_otp_code()
    redis_client.set(f"{LOGIN_OTP_PREFIX}:{user.id}", code, ex=LOGIN_OTP_TTL_SECONDS)
    send_email(
        to=user.email,
        subject="Your login code — Reunification Network",
        body=(
            f"Hi {user.full_name},\n\nYour login code is: {code}\n\n"
            f"Enter this to finish logging in. This code expires in 5 minutes. "
            f"If this wasn't you, you can ignore this email."
        ),
    )


def verify_login_otp(user_id, code: str) -> bool:
    key = f"{LOGIN_OTP_PREFIX}:{user_id}"
    stored = redis_client.get(key)
    if stored is None or stored != code:
        return False
    redis_client.delete(key)  # single use
    return True


RESEND_COOLDOWN_SECONDS = 30


def resend_login_otp(user: User) -> None:
    """Re-sends the login code for an email_otp/sms_otp account -- used by
    the "Resend code" link on the 2FA login screen when the first code
    didn't arrive or expired. A short per-user cooldown (Redis SETNX-style)
    stops someone from spamming the resend button into a flood of emails/SMS;
    it does NOT reset the code's own TTL further than a fresh send_login_otp/
    send_login_sms_otp call already does. Not applicable to TOTP -- an
    authenticator app's code isn't something the server sends, it's raised
    as a 400 by the route before this is ever called."""
    cooldown_key = f"{RESEND_COOLDOWN_PREFIX}:{user.id}"
    if not redis_client.set(cooldown_key, "1", ex=RESEND_COOLDOWN_SECONDS, nx=True):
        ttl = redis_client.ttl(cooldown_key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait a bit before requesting another code.",
            headers={"Retry-After": str(ttl if ttl and ttl > 0 else RESEND_COOLDOWN_SECONDS)},
        )
    if user.email_otp_enabled:
        send_login_otp(user)
    elif user.sms_otp_enabled:
        send_login_sms_otp(user)


# ---------------------------------------------------------------------------
# Two-factor auth: SMS OTP (second alternative to TOTP)
# ---------------------------------------------------------------------------
# Same no-secret-stored design as email OTP, and reuses the same Redis key
# prefixes/TTLs and _generate_otp_code() -- the code format and verification
# logic are identical, only the delivery channel (SMS vs email) and the
# enabling flag differ. verify_login_otp() above already works for both.


def start_sms_otp_setup(db: Session, user: User, phone_number: str) -> None:
    """Sends a confirmation code by SMS to the given number -- proves the
    person setting this up actually controls that phone before enabling it.
    The number isn't saved to the account until confirm_sms_otp_setup
    succeeds, same as totp_secret staying provisional until TOTP setup is
    confirmed."""
    if user.sms_otp_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SMS OTP is already enabled. Disable it first to reconfigure.",
        )
    if user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have authenticator-app 2FA enabled. Disable it first to switch methods.",
        )
    if user.email_otp_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have email-based 2FA enabled. Disable it first to switch methods.",
        )
    code = _generate_otp_code()
    # Stash the pending phone number alongside the code so
    # confirm_sms_otp_setup can save the *verified* number, not whatever the
    # request claims at confirmation time (the two calls could otherwise
    # race with a different number in between).
    redis_client.set(
        f"{SETUP_OTP_PREFIX}:{user.id}", json.dumps({"code": code, "phone_number": phone_number}),
        ex=SETUP_OTP_TTL_SECONDS,
    )
    send_sms(
        to=phone_number,
        body=f"Your Reunification Network confirmation code is: {code}. Expires in 10 minutes.",
    )


def confirm_sms_otp_setup(db: Session, user: User, code: str) -> User:
    key = f"{SETUP_OTP_PREFIX}:{user.id}"
    stored = redis_client.get(key)
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Incorrect or expired code. Request a new one and try again.",
    )
    if stored is None:
        raise invalid
    try:
        pending = json.loads(stored)
    except (TypeError, ValueError):
        raise invalid
    if pending.get("code") != code:
        raise invalid
    redis_client.delete(key)
    user.phone_number = pending["phone_number"]
    user.sms_otp_enabled = True
    db.commit()
    db.refresh(user)
    return user


def disable_sms_otp(db: Session, user: User) -> User:
    """No code challenge required to disable -- same reasoning as
    disable_email_otp: the person is already authenticated with a valid
    access token."""
    if not user.sms_otp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMS OTP is not enabled on this account.",
        )
    user.sms_otp_enabled = False
    db.commit()
    db.refresh(user)
    return user


def send_login_sms_otp(user: User) -> None:
    """Called from the /auth/login route when a user with sms_otp_enabled
    passes the password check -- sends the code they'll need for
    /auth/2fa/login. Shares LOGIN_OTP_PREFIX with email OTP (see
    verify_login_otp) since only one method can be enabled at a time."""
    code = _generate_otp_code()
    redis_client.set(f"{LOGIN_OTP_PREFIX}:{user.id}", code, ex=LOGIN_OTP_TTL_SECONDS)
    send_sms(
        to=user.phone_number,
        body=f"Your Reunification Network login code is: {code}. Expires in 5 minutes.",
    )
