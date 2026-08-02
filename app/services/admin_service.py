import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.services.auth_service import revoke_all_sessions


def list_pending_authority_requests(db: Session) -> list[User]:
    stmt = select(User).where(User.role == UserRole.AUTHORITY, User.is_verified.is_(False))
    return list(db.scalars(stmt))


def approve_authority(db: Session, user_id: uuid.UUID, admin: User) -> User:
    user = db.get(User, user_id)
    if user is None or user.role != UserRole.AUTHORITY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Authority request not found"
        )

    user.is_verified = True
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="user.authority_approved",
            target_type="user",
            target_id=user.id,
            log_metadata={"org_name": user.org_name},
        )
    )
    db.commit()
    db.refresh(user)
    return user


def list_users(
    db: Session,
    role_filter: UserRole | None = None,
    is_active_filter: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[User]:
    """Backs the admin dashboard's user list -- needed so an admin has a way
    to find a user_id to deactivate/reactivate in the first place."""
    stmt = select(User).order_by(User.email).limit(limit).offset(offset)
    if role_filter is not None:
        stmt = stmt.where(User.role == role_filter)
    if is_active_filter is not None:
        stmt = stmt.where(User.is_active == is_active_filter)
    return list(db.scalars(stmt))


def deactivate_user(db: Session, user_id: uuid.UUID, admin: User) -> User:
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You can't deactivate your own account.",
        )
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="user.deactivated",
            target_type="user",
            target_id=user.id,
            log_metadata={},
        )
    )
    db.commit()
    db.refresh(user)

    # Belt-and-suspenders beyond get_current_user's is_active check: this
    # also kills every existing session immediately, rather than waiting for
    # the (short-lived) access token to naturally expire.
    revoke_all_sessions(user.id)
    return user


def reactivate_user(db: Session, user_id: uuid.UUID, admin: User) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = True
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="user.reactivated",
            target_type="user",
            target_id=user.id,
            log_metadata={},
        )
    )
    db.commit()
    db.refresh(user)
    return user


def list_audit_logs(
    db: Session,
    target_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditLog]:
    """Backs the admin audit-log viewer. The AuditLog table has been written
    to since Phase 1 (every case status change, sighting review, and
    authority approval) but had no read path until now."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    if target_type is not None:
        stmt = stmt.where(AuditLog.target_type == target_type)
    return list(db.scalars(stmt))
