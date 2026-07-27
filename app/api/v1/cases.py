import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.case import CaseStatus
from app.models.user import User
from app.schemas.case import CaseCreate, CaseListItem, CaseRead, CaseStatusUpdate, CaseUpdate
from app.services import case_service

router = APIRouter()


@router.post("", response_model=CaseRead, status_code=201)
def create_case(
    payload: CaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseRead:
    case = case_service.create_case(db, payload, reporter=current_user)
    return CaseRead.model_validate(case)


@router.get("", response_model=list[CaseListItem])
def list_cases(
    status_filter: CaseStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[CaseListItem]:
    """Public — browse cases. No auth required, matches FR-5."""
    cases = case_service.list_cases(db, status_filter, limit, offset)
    return [CaseListItem.model_validate(c) for c in cases]


@router.get("/{case_id}", response_model=CaseRead)
def get_case(case_id: uuid.UUID, db: Session = Depends(get_db)) -> CaseRead:
    """Public — case detail. No auth required, matches FR-5."""
    case = case_service.get_case_or_404(db, case_id)
    return CaseRead.model_validate(case)


@router.patch("/{case_id}", response_model=CaseRead)
def update_case(
    case_id: uuid.UUID,
    payload: CaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseRead:
    case = case_service.get_case_or_404(db, case_id)
    updated = case_service.update_case(db, case, payload, current_user)
    return CaseRead.model_validate(updated)


@router.patch("/{case_id}/status", response_model=CaseRead)
def update_case_status(
    case_id: uuid.UUID,
    payload: CaseStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseRead:
    """TODO(phase-3): restrict to authority/admin roles via require_role(),
    and to the assigned authority specifically at the row level. Currently
    any authenticated user can call this — role enforcement lands in Phase 3."""
    case = case_service.get_case_or_404(db, case_id)
    updated = case_service.update_case_status(db, case, payload.status, actor=current_user)
    return CaseRead.model_validate(updated)
