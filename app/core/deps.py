import uuid
from collections.abc import Iterable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import InvalidTokenError, decode_token
from app.db.session import get_db
from app.models.user import User, UserRole

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


def require_role(*roles: UserRole):
    """Dependency factory: returns a dependency that 403s unless the current
    user's role is one of `roles`. Usage: Depends(require_role(UserRole.ADMIN)).

    Stacks on top of get_current_user, so it also 401s if there's no valid
    token at all — a missing/invalid token and a wrong role are different
    failure modes and get different status codes.
    """
    allowed: Iterable[UserRole] = roles

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of these roles: {', '.join(r.value for r in allowed)}",
            )
        return current_user

    return dependency


def require_verified_authority_or_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Stricter than require_role(AUTHORITY, ADMIN): an authority account that
    hasn't been approved by an admin yet (is_verified=False) is blocked too.
    Use this for review/status-change endpoints rather than plain
    require_role(), since an unverified authority shouldn't act as one yet."""
    if current_user.role == UserRole.ADMIN:
        return current_user
    if current_user.role == UserRole.AUTHORITY and current_user.is_verified:
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="This action requires a verified authority or admin account",
    )
