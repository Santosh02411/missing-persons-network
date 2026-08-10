from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.case_collaborator import CaseCollaborator
from app.models.case_note import CaseNote
from app.models.user import User, UserRole
from app.services.case_service import has_case_access, is_case_collaborator


def _require_case_access(db: Session, case: Case, actor: User) -> None:
    if not has_case_access(db, case, actor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned authority, a collaborator on this case, or an admin can do this",
        )


# ------------------------------------------------------------------- notes


def add_case_note(db: Session, case: Case, body: str, author: User) -> dict:
    _require_case_access(db, case, author)
    note = CaseNote(case_id=case.id, author_id=author.id, body=body)
    db.add(note)
    db.commit()
    db.refresh(note)
    return {
        "id": note.id,
        "case_id": note.case_id,
        "author_id": note.author_id,
        "author_name": author.full_name,
        "body": note.body,
        "created_at": note.created_at,
    }


def list_case_notes(db: Session, case: Case, actor: User) -> list[dict]:
    """Private, internal investigation log -- never visible to the reporter
    or the public, only to whoever has case access (see has_case_access)."""
    _require_case_access(db, case, actor)
    stmt = (
        select(CaseNote, User.full_name)
        .join(User, User.id == CaseNote.author_id)
        .where(CaseNote.case_id == case.id)
        .order_by(CaseNote.created_at.desc())
    )
    return [
        {
            "id": note.id,
            "case_id": note.case_id,
            "author_id": note.author_id,
            "author_name": author_name,
            "body": note.body,
            "created_at": note.created_at,
        }
        for note, author_name in db.execute(stmt)
    ]


# ------------------------------------------------------------ collaborators


def add_collaborator(db: Session, case: Case, authority_id, actor: User) -> dict:
    """Gives another verified authority/NGO account the same access to this
    case as the primary assigned_authority (case_service.has_case_access) --
    editing, status changes, sharing, and notes. Only the case's current
    assigned authority or an admin can add collaborators; a collaborator
    can't themselves add further collaborators, to keep one clear owner in
    charge of who else gets pulled into a case."""
    is_admin = actor.role == UserRole.ADMIN
    is_assigned_authority = (
        actor.role == UserRole.AUTHORITY and case.assigned_authority_id == actor.id
    )
    if not (is_admin or is_assigned_authority):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned authority or an admin can add collaborators",
        )

    authority = db.get(User, authority_id)
    if authority is None or authority.role != UserRole.AUTHORITY or not authority.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That account isn't a valid, verified authority.",
        )
    if authority.id == case.assigned_authority_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That authority is already the assigned authority on this case.",
        )
    if is_case_collaborator(db, case.id, authority.id):
        return get_collaborator(db, case.id, authority.id)  # idempotent

    collab = CaseCollaborator(case_id=case.id, user_id=authority.id, added_by=actor.id)
    db.add(collab)
    db.add(
        AuditLog(
            actor_id=actor.id,
            action="case.collaborator_added",
            target_type="case",
            target_id=case.id,
            log_metadata={"collaborator_id": str(authority.id)},
        )
    )
    db.commit()
    return get_collaborator(db, case.id, authority.id)


def remove_collaborator(db: Session, case: Case, user_id, actor: User) -> None:
    """A collaborator can remove themselves; otherwise only the assigned
    authority or an admin can remove someone."""
    is_admin = actor.role == UserRole.ADMIN
    is_assigned_authority = (
        actor.role == UserRole.AUTHORITY and case.assigned_authority_id == actor.id
    )
    is_self = actor.id == user_id
    if not (is_admin or is_assigned_authority or is_self):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned authority, an admin, or the collaborator themselves can remove this",
        )

    stmt = select(CaseCollaborator).where(
        CaseCollaborator.case_id == case.id, CaseCollaborator.user_id == user_id
    )
    collab = db.scalars(stmt).first()
    if collab is None:
        return  # not a collaborator -- idempotent, not an error
    db.delete(collab)
    db.add(
        AuditLog(
            actor_id=actor.id,
            action="case.collaborator_removed",
            target_type="case",
            target_id=case.id,
            log_metadata={"collaborator_id": str(user_id)},
        )
    )
    db.commit()


def get_collaborator(db: Session, case_id, user_id) -> dict:
    stmt = (
        select(CaseCollaborator, User.full_name, User.org_name)
        .join(User, User.id == CaseCollaborator.user_id)
        .where(CaseCollaborator.case_id == case_id, CaseCollaborator.user_id == user_id)
    )
    collab, full_name, org_name = db.execute(stmt).one()
    return {
        "user_id": collab.user_id,
        "full_name": full_name,
        "org_name": org_name,
        "added_by": collab.added_by,
        "created_at": collab.created_at,
    }


def list_collaborators(db: Session, case: Case, actor: User) -> list[dict]:
    _require_case_access(db, case, actor)
    stmt = (
        select(CaseCollaborator, User.full_name, User.org_name)
        .join(User, User.id == CaseCollaborator.user_id)
        .where(CaseCollaborator.case_id == case.id)
        .order_by(CaseCollaborator.created_at)
    )
    return [
        {
            "user_id": collab.user_id,
            "full_name": full_name,
            "org_name": org_name,
            "added_by": collab.added_by,
            "created_at": collab.created_at,
        }
        for collab, full_name, org_name in db.execute(stmt)
    ]
