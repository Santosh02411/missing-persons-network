import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import bump_cases_list_version
from app.models.audit_log import AuditLog
from app.models.case import Case, CaseStatus
from app.models.user import User, UserRole
from app.schemas.case import CaseCreate, CaseUpdate
from app.services.geo_service import to_geography


def create_case(db: Session, payload: CaseCreate, reporter: User) -> Case:
    case = Case(
        created_by=reporter.id,
        name=payload.name,
        age_at_disappearance=payload.age_at_disappearance,
        photo_url=payload.photo_url,
        description=payload.description,
        last_seen_location=to_geography(payload.last_seen_location),
        last_seen_address=payload.last_seen_address,
        last_seen_at=payload.last_seen_at,
        status=CaseStatus.OPEN,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    bump_cases_list_version()
    return case


def get_case_or_404(db: Session, case_id: uuid.UUID) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return case


def list_cases(db: Session, status_filter: CaseStatus | None, limit: int, offset: int) -> list[Case]:
    stmt = select(Case).order_by(Case.created_at.desc()).limit(limit).offset(offset)
    if status_filter is not None:
        stmt = stmt.where(Case.status == status_filter)
    return list(db.scalars(stmt))


def update_case(db: Session, case: Case, payload: CaseUpdate, current_user: User) -> Case:
    # Ownership check: the reporter who created the case, the assigned
    # authority, or an admin may edit it. Role membership itself (must be
    # authority/admin to be "assigned" at all) is enforced via require_role()
    # at the route level for the status endpoint; this is the row-level half.
    is_owner = case.created_by == current_user.id
    is_assigned_authority = (
        current_user.role == UserRole.AUTHORITY
        and case.assigned_authority_id == current_user.id
    )
    is_admin = current_user.role == UserRole.ADMIN

    if not (is_owner or is_assigned_authority or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the reporter, the assigned authority, or an admin can edit this case",
        )

    data = payload.model_dump(exclude_unset=True)
    if "last_seen_location" in data and data["last_seen_location"] is not None:
        case.last_seen_location = to_geography(payload.last_seen_location)
        data.pop("last_seen_location")
    for field, value in data.items():
        setattr(case, field, value)

    db.commit()
    db.refresh(case)
    bump_cases_list_version()
    return case


def claim_case(db: Session, case: Case, actor: User) -> Case:
    """An authority/admin takes ownership of a case (route-level require_role
    already ensures actor is authority-or-admin). A case can only be claimed
    once; re-claiming an already-assigned case is rejected rather than
    silently reassigning it, to avoid one authority stepping on another's
    active investigation."""
    if case.assigned_authority_id is not None and case.assigned_authority_id != actor.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This case is already assigned to another authority",
        )

    case.assigned_authority_id = actor.id
    db.add(
        AuditLog(
            actor_id=actor.id,
            action="case.claimed",
            target_type="case",
            target_id=case.id,
            log_metadata={},
        )
    )
    db.commit()
    db.refresh(case)
    bump_cases_list_version()
    return case


def update_case_status(
    db: Session, case: Case, new_status: CaseStatus, actor: User
) -> Case:
    # Route-level require_verified_authority_or_admin already ensures actor's
    # role qualifies; this enforces the row-level rule that only *this
    # case's* assigned authority (or an admin) may change its status.
    is_assigned_authority = (
        actor.role == UserRole.AUTHORITY and case.assigned_authority_id == actor.id
    )
    is_admin = actor.role == UserRole.ADMIN
    if not (is_assigned_authority or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned authority or an admin can change this case's status",
        )

    old_status = case.status
    case.status = new_status
    db.add(
        AuditLog(
            actor_id=actor.id,
            action="case.status_changed",
            target_type="case",
            target_id=case.id,
            log_metadata={"from": old_status.value, "to": new_status.value},
        )
    )
    db.commit()
    db.refresh(case)
    bump_cases_list_version()
    return case
