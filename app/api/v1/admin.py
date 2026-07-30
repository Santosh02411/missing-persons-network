import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.audit_log import AuditLogRead
from app.schemas.user import UserRead
from app.services import admin_service

router = APIRouter()


@router.get("/authority-requests", response_model=list[UserRead])
def list_authority_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> list[UserRead]:
    """Admin only."""
    users = admin_service.list_pending_authority_requests(db)
    return [UserRead.model_validate(u) for u in users]


@router.post("/authority-requests/{user_id}/approve", response_model=UserRead)
def approve_authority_request(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> UserRead:
    """Admin only."""
    user = admin_service.approve_authority(db, user_id, admin=current_user)
    return UserRead.model_validate(user)


@router.get("/audit-logs", response_model=list[AuditLogRead])
def list_audit_logs(
    target_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> list[AuditLogRead]:
    """Admin only. The AuditLog table has recorded every case status change,
    sighting review, and authority approval since Phase 1 -- this is the
    first endpoint that actually reads it back."""
    logs = admin_service.list_audit_logs(db, target_type, limit, offset)
    return [AuditLogRead.model_validate(log) for log in logs]


@router.get("/users", response_model=list[UserRead])
def list_users(
    role: UserRole | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> list[UserRead]:
    """Admin only. Needed so an admin has a way to find a user_id to
    deactivate/reactivate in the first place."""
    users = admin_service.list_users(db, role, is_active, limit, offset)
    return [UserRead.model_validate(u) for u in users]


@router.post("/users/{user_id}/deactivate", response_model=UserRead)
def deactivate_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> UserRead:
    """Admin only. Sets is_active=False (already enforced by
    get_current_user and the refresh route) and immediately revokes every
    existing session for that user, rather than waiting for their current
    access token to expire on its own."""
    user = admin_service.deactivate_user(db, user_id, admin=current_user)
    return UserRead.model_validate(user)


@router.post("/users/{user_id}/reactivate", response_model=UserRead)
def reactivate_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> UserRead:
    """Admin only."""
    user = admin_service.reactivate_user(db, user_id, admin=current_user)
    return UserRead.model_validate(user)
