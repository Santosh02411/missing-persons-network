import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db.session import get_db
from app.models.user import User, UserRole
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
