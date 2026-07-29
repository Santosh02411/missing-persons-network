from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.token import (
    EmailVerifyRequest,
    ForgotPasswordRequest,
    RefreshRequest,
    ResetPasswordRequest,
    Token,
)
from app.schemas.user import UserCreate, UserLogin, UserRead
from app.services.auth_service import (
    authenticate_user,
    is_refresh_jti_valid,
    register_user,
    request_password_reset,
    reset_password,
    revoke_refresh_token,
    send_verification_email,
    store_refresh_jti,
    verify_email_token,
)

router = APIRouter()


def _issue_tokens(user_id) -> Token:
    access_token = create_access_token(user_id)
    refresh_token, jti = create_refresh_token(user_id)
    store_refresh_jti(user_id, jti)
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    """Register a new account. Authority-role signups are created with
    is_verified=False and can't review sightings or change case status until
    an admin approves them (see /api/v1/admin/authority-requests). A
    verification email (logged, not actually sent -- see core/email.py) goes
    out immediately; email_verified doesn't block anything yet."""
    return register_user(db, payload)


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    """Locked out for LOGIN_LOCKOUT_SECONDS after LOGIN_FAILURE_THRESHOLD
    consecutive failures for this email (see auth_service's Redis-backed
    counter) -- returns 429 with Retry-After while locked."""
    user = authenticate_user(db, payload.email, payload.password)
    return _issue_tokens(user.id)


@router.post("/refresh", response_model=Token)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> Token:
    """Rotates the refresh token: each call invalidates the previous one and
    issues a new access + refresh pair. If a refresh token is presented whose
    jti doesn't match what's stored (e.g. an old, already-rotated token being
    reused -- a classic sign of token theft), the whole refresh session for
    that user is revoked and they must log in again."""
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
    )
    try:
        data = decode_refresh_token(payload.refresh_token)
    except InvalidTokenError as exc:
        raise invalid from exc

    user = db.get(User, data["user_id"])
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer active"
        )

    if not is_refresh_jti_valid(user.id, data["jti"]):
        # Reused/stale refresh token -- kill the session rather than silently
        # rejecting, in case this is a stolen token being replayed.
        revoke_refresh_token(user.id)
        raise invalid

    return _issue_tokens(user.id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(current_user: User = Depends(get_current_user)) -> None:
    """Revokes the current user's refresh token server-side. The access
    token already issued keeps working until it naturally expires (it's
    stateless by design) -- logout mainly prevents further refreshes."""
    revoke_refresh_token(current_user.id)


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Lets the frontend identify who's logged in (and their role) after a
    page reload, when it has an access token but no in-memory user object."""
    return current_user


@router.post("/verify-email", response_model=UserRead)
def verify_email(payload: EmailVerifyRequest, db: Session = Depends(get_db)) -> User:
    """Confirms the token from the emailed verification link and marks the
    account's email_verified=True. Doesn't require auth -- the token itself
    is the proof of identity, since the user may not be logged in (or may
    have just registered) when they click the link."""
    return verify_email_token(db, payload.token)


@router.post("/resend-verification", status_code=status.HTTP_204_NO_CONTENT)
def resend_verification(current_user: User = Depends(get_current_user)) -> None:
    """Re-sends the verification email for the logged-in user. No rate
    limiting on this yet -- worth adding if this project goes further, since
    it's an unauthenticated-adjacent way to trigger outbound "email" sends."""
    send_verification_email(current_user)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict:
    """Always returns 202 with the same generic message whether or not the
    email is registered -- this prevents using this endpoint to enumerate
    which emails have accounts. The actual reset email is only sent
    internally if the account exists (see auth_service.request_password_reset)."""
    request_password_reset(db, payload.email)
    return {"detail": "If that email is registered, a password reset link has been sent."}


@router.post("/reset-password", response_model=UserRead)
def reset_password_route(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> User:
    """Consumes a one-time reset token (1 hour TTL) and sets a new password.
    Also revokes the user's current refresh session, so a stolen
    password/session doesn't survive a reset."""
    return reset_password(db, payload.token, payload.new_password)
