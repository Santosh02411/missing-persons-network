import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User, UserRole


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
