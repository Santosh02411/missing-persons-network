import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.case import Case, CaseStatus
from app.models.user import User
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
    # Ownership check: only the reporter who created the case may edit it here.
    # TODO(phase-3): extend to allow the assigned authority to edit assigned cases,
    # enforced via require_role() + row-level check together.
    if case.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the reporter who created this case can edit it",
        )

    data = payload.model_dump(exclude_unset=True)
    if "last_seen_location" in data and data["last_seen_location"] is not None:
        case.last_seen_location = to_geography(payload.last_seen_location)
        data.pop("last_seen_location")
    for field, value in data.items():
        setattr(case, field, value)

    db.commit()
    db.refresh(case)
    return case


def update_case_status(
    db: Session, case: Case, new_status: CaseStatus, actor: User
) -> Case:
    # TODO(phase-3): gate this endpoint to authority/admin roles via require_role(),
    # and to only the *assigned* authority at the row level.
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
    return case
