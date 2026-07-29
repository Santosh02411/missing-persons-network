import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import InvalidTokenError, decode_token
from app.db.session import get_db
from app.models.user import User

# tokenUrl points at the login route for OpenAPI docs' "Authorize" button.
# Login itself uses a JSON body (UserLogin), not form data — see api/v1/auth.py.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise credentials_exception

    try:
        user_id: uuid.UUID = decode_token(token, expected_type="access")
    except InvalidTokenError as exc:
        raise credentials_exception from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """For endpoints that behave differently for logged-in vs anonymous users
    (e.g. sighting submission, which allows anonymous tips) but don't require auth."""
    if token is None:
        return None
    try:
        return get_current_user(token=token, db=db)
    except HTTPException:
        return None


# NOTE (Phase 3): role-based gating — require_role(*roles) — and row-level
# ownership checks (e.g. "only the assigned authority can change this case's
# status") land here in Phase 3. Endpoints that will need it are marked
# `# TODO(phase-3)` at their call sites.
