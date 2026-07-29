from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.deps import get_current_user
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.token import RefreshRequest, Token
from app.schemas.user import UserCreate, UserLogin, UserRead
from app.services.auth_service import (
    authenticate_user,
    is_refresh_jti_valid,
    register_user,
    revoke_refresh_token,
    store_refresh_jti,
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
    an admin approves them (see /api/v1/admin/authority-requests)."""
    return register_user(db, payload)


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
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
