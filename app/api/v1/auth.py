from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_session_id, get_current_user, require_role
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_mfa_token,
    create_refresh_token,
    decode_refresh_token,
    decode_token,
)
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.token import (
    EmailVerifyRequest,
    ForgotPasswordRequest,
    LoginResult,
    RefreshRequest,
    ResetPasswordRequest,
    SessionRead,
    Token,
    TwoFactorCodeRequest,
    TwoFactorLoginRequest,
    TwoFactorSetupResponse,
)
from app.schemas.user import UserCreate, UserLogin, UserRead
from app.services.auth_service import (
    authenticate_user,
    confirm_email_otp_setup,
    confirm_totp_setup,
    create_session_id,
    disable_email_otp,
    disable_totp,
    is_refresh_jti_valid,
    list_sessions,
    register_user,
    request_password_reset,
    reset_password,
    revoke_all_sessions,
    revoke_session,
    send_login_otp,
    send_verification_email,
    start_email_otp_setup,
    start_totp_setup,
    store_refresh_jti,
    verify_login_otp,
)

router = APIRouter()


def _issue_tokens(user_id, sid: str) -> Token:
    access_token = create_access_token(user_id, sid)
    refresh_token, jti = create_refresh_token(user_id, sid)
    store_refresh_jti(user_id, sid, jti)
    return Token(access_token=access_token, refresh_token=refresh_token)


def _issue_tokens_new_session(user_id, user_agent: str | None) -> Token:
    """Used at login/register -- starts a brand-new session (new sid), which
    is what makes multi-device support work: logging in on a second device
    doesn't touch the first device's session at all."""
    sid = create_session_id()
    access_token = create_access_token(user_id, sid)
    refresh_token, jti = create_refresh_token(user_id, sid)
    store_refresh_jti(user_id, sid, jti, user_agent=user_agent)
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    """Register a new account. Authority-role signups are created with
    is_verified=False and can't review sightings or change case status until
    an admin approves them (see /api/v1/admin/authority-requests). A
    verification email (logged, not actually sent -- see core/email.py) goes
    out immediately; email_verified doesn't block anything yet."""
    return register_user(db, payload)


@router.post("/login", response_model=LoginResult)
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)) -> LoginResult:
    """Locked out for LOGIN_LOCKOUT_SECONDS after LOGIN_FAILURE_THRESHOLD
    consecutive failures for this email (429 + Retry-After).

    If the account has two-factor auth enabled (either method), this does
    NOT issue tokens directly -- it returns {mfa_required: true, mfa_token,
    mfa_method}. For mfa_method="totp" the caller enters a code from their
    authenticator app; for "email_otp" a fresh code has already been emailed
    by this call, and the caller enters that. Either way, completing login
    happens at POST /auth/2fa/login with that mfa_token plus the code."""
    user = authenticate_user(db, payload.email, payload.password)

    if user.totp_enabled:
        return LoginResult(
            mfa_required=True, mfa_token=create_mfa_token(user.id), mfa_method="totp"
        )
    if user.email_otp_enabled:
        send_login_otp(user)
        return LoginResult(
            mfa_required=True, mfa_token=create_mfa_token(user.id), mfa_method="email_otp"
        )

    user_agent = request.headers.get("user-agent")
    tokens = _issue_tokens_new_session(user.id, user_agent)
    return LoginResult(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/2fa/login", response_model=Token)
def login_with_2fa(
    payload: TwoFactorLoginRequest, request: Request, db: Session = Depends(get_db)
) -> Token:
    """Completes login for a 2FA-enabled account: the mfa_token proves the
    password check already passed (see /auth/login), and the code proves
    possession of the authenticator app or the registered email inbox,
    whichever method is enabled on the account."""
    from app.core.totp import verify_totp_code

    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired login session, or incorrect code. Please try logging in again.",
    )
    try:
        user_id = decode_token(payload.mfa_token, expected_type="mfa")
    except InvalidTokenError as exc:
        raise invalid from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise invalid

    if user.totp_enabled:
        if not user.totp_secret or not verify_totp_code(user.totp_secret, payload.code):
            raise invalid
    elif user.email_otp_enabled:
        if not verify_login_otp(user.id, payload.code):
            raise invalid
    else:
        raise invalid

    user_agent = request.headers.get("user-agent")
    return _issue_tokens_new_session(user.id, user_agent)


@router.post("/refresh", response_model=Token)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> Token:
    """Rotates the refresh token within the SAME session (sid unchanged,
    only the jti and the tokens themselves change). If a refresh token is
    presented whose jti doesn't match what's stored for that session (e.g.
    an old, already-rotated token being reused -- a sign of token theft),
    that one session is revoked and its owner must log in again -- other
    sessions/devices for the same user are unaffected."""
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

    if not is_refresh_jti_valid(user.id, data["sid"], data["jti"]):
        revoke_session(user.id, data["sid"])
        raise invalid

    return _issue_tokens(user.id, data["sid"])


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current_user: User = Depends(get_current_user),
    session_id: str = Depends(get_current_session_id),
) -> None:
    """Revokes only the CURRENT session/device -- other devices the user is
    logged in on are untouched. Use /auth/logout-all to sign out everywhere."""
    revoke_session(current_user.id, session_id)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(current_user: User = Depends(get_current_user)) -> None:
    """Signs out every device/session for the current user."""
    revoke_all_sessions(current_user.id)


@router.get("/sessions", response_model=list[SessionRead])
def get_sessions(current_user: User = Depends(get_current_user)) -> list[SessionRead]:
    """Lists the current user's active sessions ('your devices') -- lets
    someone notice a login they don't recognize and revoke it."""
    return [SessionRead(**s) for s in list_sessions(current_user.id)]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, current_user: User = Depends(get_current_user)) -> None:
    """Revokes a specific session by id -- e.g. remotely logging out a lost
    device. Safe by construction even without an extra ownership check:
    session keys are namespaced by user_id in Redis, so this can only ever
    touch a session belonging to current_user regardless of what session_id
    is passed."""
    revoke_session(current_user.id, session_id)


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
    from app.services.auth_service import verify_email_token

    return verify_email_token(db, payload.token)


@router.post("/resend-verification", status_code=status.HTTP_204_NO_CONTENT)
def resend_verification(current_user: User = Depends(get_current_user)) -> None:
    """Re-sends the verification email for the logged-in user."""
    send_verification_email(current_user)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict:
    """Always returns 202 with the same generic message whether or not the
    email is registered -- prevents using this endpoint to enumerate which
    emails have accounts."""
    request_password_reset(db, payload.email)
    return {"detail": "If that email is registered, a password reset link has been sent."}


@router.post("/reset-password", response_model=UserRead)
def reset_password_route(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> User:
    """Consumes a one-time reset token (1 hour TTL), sets a new password, and
    revokes every existing session for that user (all devices)."""
    return reset_password(db, payload.token, payload.new_password)


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
def setup_2fa(
    current_user: User = Depends(require_role(UserRole.AUTHORITY, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> TwoFactorSetupResponse:
    """Starts two-factor setup. Restricted to authority/admin roles (per
    docs/SECURITY_AND_ACCESS.md) -- these are the accounts that can approve
    other authorities, verify sightings, or change case status, so they
    carry more risk if compromised. Returns a secret + otpauth:// URI for the
    frontend to render as a QR code; totp_enabled stays False until
    confirmed via /auth/2fa/verify."""
    secret, uri = start_totp_setup(db, current_user)
    return TwoFactorSetupResponse(secret=secret, otpauth_uri=uri)


@router.post("/2fa/verify", response_model=UserRead)
def verify_2fa_setup(
    payload: TwoFactorCodeRequest,
    current_user: User = Depends(require_role(UserRole.AUTHORITY, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> User:
    """Confirms setup by checking a code from the authenticator app. Only
    after this succeeds does totp_enabled flip to True and future logins
    start requiring a code."""
    return confirm_totp_setup(db, current_user, payload.code)


@router.post("/2fa/disable", response_model=UserRead)
def disable_2fa_route(
    payload: TwoFactorCodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Requires a current, valid TOTP code to disable -- so a stolen access
    token alone isn't enough to turn off 2FA on an account."""
    return disable_totp(db, current_user, payload.code)


@router.post("/2fa/email-otp/setup", status_code=status.HTTP_202_ACCEPTED)
def setup_email_otp(
    current_user: User = Depends(require_role(UserRole.AUTHORITY, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    """Alternative to the authenticator-app method above: sends a
    confirmation code to the account's email instead of a QR code. Restricted
    to authority/admin the same way TOTP setup is."""
    start_email_otp_setup(db, current_user)
    return {"detail": "A confirmation code has been sent to your email."}


@router.post("/2fa/email-otp/verify", response_model=UserRead)
def verify_email_otp_setup(
    payload: TwoFactorCodeRequest,
    current_user: User = Depends(require_role(UserRole.AUTHORITY, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> User:
    """Confirms the emailed code, enabling email_otp_enabled."""
    return confirm_email_otp_setup(db, current_user, payload.code)


@router.post("/2fa/email-otp/disable", response_model=UserRead)
def disable_email_otp_route(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """No code challenge here (unlike TOTP disable) -- there's no standing
    secret proving anything, so being authenticated is sufficient."""
    return disable_email_otp(db, current_user)
