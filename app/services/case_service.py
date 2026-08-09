import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import bump_cases_list_version
from app.core.config import settings
from app.core.email import send_email, sender_address_for
from app.models.audit_log import AuditLog
from app.models.case import Case, CaseStatus
from app.models.user import User, UserRole
from app.schemas.case import CaseCreate, CaseShareRequest, CaseUpdate
from app.services.geo_service import nearest_authority, to_geography
from app.services.upload_service import read_upload_bytes
from app.services import watch_service

# How far case_service will look for a station to auto-route a case to when
# the reporter didn't pick one explicitly. Beyond this, or if no authority
# in the whole system has a jurisdiction_location set yet, the case falls
# back to target_authority_id=None (visible to any verified authority) --
# see list_pending_approval_cases() -- rather than becoming unreviewable.
AUTO_ROUTE_RADIUS_KM = 100


def _resolve_target_authority(db: Session, payload: CaseCreate) -> uuid.UUID | None:
    if payload.target_authority_id is not None:
        target = db.get(User, payload.target_authority_id)
        if (
            target is None
            or target.role != UserRole.AUTHORITY
            or not target.is_verified
            or not target.is_active
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That station isn't a valid, verified authority account.",
            )
        return target.id

    nearest = nearest_authority(db, payload.last_seen_location, radius_km=AUTO_ROUTE_RADIUS_KM)
    return nearest.id if nearest else None


def create_case(db: Session, payload: CaseCreate, reporter: User) -> Case:
    """New cases are routed to a single station -- either the reporter's
    explicit choice or the nearest verified authority to last_seen_location
    -- rather than broadcast to every police/NGO account nationwide (see
    list_pending_approval_cases). If no station can be resolved (none picked,
    none within range, or no authority has set a jurisdiction yet), the case
    is left unrouted and falls back to being visible to any verified
    authority, so it's never stuck unreviewable."""
    target_authority_id = _resolve_target_authority(db, payload)

    case = Case(
        created_by=reporter.id,
        name=payload.name,
        age_at_disappearance=payload.age_at_disappearance,
        photo_url=payload.photo_url,
        description=payload.description,
        last_seen_location=to_geography(payload.last_seen_location),
        last_seen_address=payload.last_seen_address,
        last_seen_at=payload.last_seen_at,
        status=CaseStatus.PENDING_REVIEW,
        target_authority_id=target_authority_id,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    bump_cases_list_version()
    watch_service.watch_case(db, case, reporter)
    return case


def get_case_or_404(db: Session, case_id: uuid.UUID, current_user: User | None = None) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    if case.status == CaseStatus.PENDING_REVIEW:
        # Not public yet -- only the reporter who filed it, or an
        # authority/admin (who'd need to review it to approve it), can see
        # it. 404 rather than 403 here so an unauthorized viewer can't even
        # tell the case exists.
        is_owner = current_user is not None and case.created_by == current_user.id
        is_authority_or_admin = current_user is not None and current_user.role in (
            UserRole.AUTHORITY,
            UserRole.ADMIN,
        )
        if not (is_owner or is_authority_or_admin):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    return case


def list_pending_approval_cases(
    db: Session, actor: User, limit: int = 50, offset: int = 0
) -> list[Case]:
    """Backs the authority dashboard's approval queue.

    A case is only routed to one station (see create_case), so an authority
    only sees cases either explicitly filed with them or auto-routed to them
    as the nearest station -- not every pending case nationwide. Cases that
    couldn't be routed to any station (target_authority_id is NULL) still
    show up for every verified authority, as a fallback so nothing sits
    unreviewable. Admins see everything, for oversight."""
    stmt = select(Case).where(Case.status == CaseStatus.PENDING_REVIEW)
    if actor.role != UserRole.ADMIN:
        stmt = stmt.where(
            (Case.target_authority_id == actor.id) | (Case.target_authority_id.is_(None))
        )
    stmt = stmt.order_by(Case.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


def list_assigned_cases(db: Session, authority_id) -> list[Case]:
    """Cases assigned to a specific authority -- backs the authority
    dashboard's "my cases" view. Added alongside the frontend dashboard since
    there was previously no way to ask "which cases are mine" other than
    fetching every case and filtering client-side."""
    stmt = (
        select(Case)
        .where(Case.assigned_authority_id == authority_id)
        .order_by(Case.created_at.desc())
    )
    return list(db.scalars(stmt))


def list_cases(db: Session, status_filter: CaseStatus | None, limit: int, offset: int) -> list[Case]:
    # Never publicly listed, even if someone explicitly asks for
    # ?status=pending_review -- unapproved cases aren't public. Use
    # list_pending_approval_cases() (authority/admin only) for those.
    # Dismissed (rejected/invalid) cases are excluded from the public list
    # the same way -- they're not something the public needs to browse.
    stmt = (
        select(Case)
        .where(Case.status.not_in([CaseStatus.PENDING_REVIEW, CaseStatus.DISMISSED]))
        .order_by(Case.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status_filter is not None and status_filter not in (
        CaseStatus.PENDING_REVIEW,
        CaseStatus.DISMISSED,
    ):
        stmt = stmt.where(Case.status == status_filter)
    return list(db.scalars(stmt))


def list_my_cases(db: Session, user_id) -> list[Case]:
    """All cases filed by this user, any status (including pending_review and
    dismissed) -- backs the citizen dashboard's "my cases" list. Unlike the
    public list, this deliberately shows every status, since the point is
    letting someone track what happened to their own submission."""
    stmt = select(Case).where(Case.created_by == user_id).order_by(Case.created_at.desc())
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


def _require_target_authority_or_admin(case: Case, actor: User) -> None:
    """A pending case routed to a specific station (target_authority_id set)
    can only be approved/dismissed by that station's account, or an admin --
    this is what makes routing in create_case actually mean something,
    rather than every authority still being able to act on every case. A
    case with no resolved target (target_authority_id is None) stays open
    to any verified authority, matching the fallback in
    list_pending_approval_cases."""
    if actor.role == UserRole.ADMIN:
        return
    if case.target_authority_id is not None and case.target_authority_id != actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This case was filed with a different police station or NGO authority.",
        )


def approve_case(db: Session, case: Case, actor: User) -> Case:
    """An authority/admin approves a newly-filed case, making it public and
    simultaneously claiming it (the approving authority becomes the assigned
    one -- they already reviewed it, so they're the natural owner). Route-
    level require_verified_authority_or_admin already ensures actor's role
    qualifies."""
    if case.status != CaseStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This case has already been reviewed.",
        )
    _require_target_authority_or_admin(case, actor)

    case.status = CaseStatus.OPEN
    case.assigned_authority_id = actor.id
    db.add(
        AuditLog(
            actor_id=actor.id,
            action="case.approved",
            target_type="case",
            target_id=case.id,
            log_metadata={},
        )
    )
    db.commit()
    db.refresh(case)
    bump_cases_list_version()
    watch_service.notify_watchers(
        db, case,
        headline="This case has been approved and is now public.",
        detail="Status: Open.",
        exclude_user_id=actor.id,
    )
    return case


def claim_case(db: Session, case: Case, actor: User) -> Case:
    """An authority/admin takes ownership of a case (route-level require_role
    already ensures actor is authority-or-admin). A case can only be claimed
    once; re-claiming an already-assigned case is rejected rather than
    silently reassigning it, to avoid one authority stepping on another's
    active investigation."""
    if case.status == CaseStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This case hasn't been approved yet -- use the approve action instead.",
        )
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


def dismiss_case(db: Session, case: Case, actor: User, reason: str | None = None) -> Case:
    """Rejects a case -- either a pending_review submission judged fake/
    invalid, or an approved case closed without a resolution. Admins can
    dismiss any case; authorities can only dismiss a case that's still
    pending review (anyone reviewing can reject it) or already assigned to
    them specifically (not another authority's active case)."""
    if case.status in (CaseStatus.RESOLVED, CaseStatus.DISMISSED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This case is already closed."
        )

    is_admin = actor.role == UserRole.ADMIN
    is_targeted_pending = (
        case.status == CaseStatus.PENDING_REVIEW
        and actor.role == UserRole.AUTHORITY
        and (case.target_authority_id is None or case.target_authority_id == actor.id)
    )
    is_assigned_authority = (
        actor.role == UserRole.AUTHORITY and case.assigned_authority_id == actor.id
    )
    if not (is_admin or is_targeted_pending or is_assigned_authority):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the station this case was filed with, the assigned authority, or an admin can dismiss this case",
        )

    old_status = case.status
    case.status = CaseStatus.DISMISSED
    db.add(
        AuditLog(
            actor_id=actor.id,
            action="case.dismissed",
            target_type="case",
            target_id=case.id,
            log_metadata={"from": old_status.value, "reason": reason},
        )
    )
    db.commit()
    db.refresh(case)
    bump_cases_list_version()
    watch_service.notify_watchers(
        db, case,
        headline="This case has been dismissed.",
        detail=reason or "No reason was given.",
        exclude_user_id=actor.id,
    )
    return case


def update_case_status(
    db: Session, case: Case, new_status: CaseStatus, actor: User
) -> Case:
    if new_status in (CaseStatus.PENDING_REVIEW, CaseStatus.DISMISSED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use the approve/dismiss actions for these transitions, not a direct status update.",
        )
    if case.status in (CaseStatus.RESOLVED, CaseStatus.DISMISSED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This case is already closed."
        )

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
    watch_service.notify_watchers(
        db, case,
        headline=f"This case's status changed to {new_status.value.replace('_', ' ').title()}.",
        detail=f"Previously: {old_status.value.replace('_', ' ').title()}.",
        exclude_user_id=actor.id,
    )
    return case


def _load_case_photo(case: Case) -> tuple[str, bytes] | None:
    """(filename, bytes) for the case's photo, for use as an email
    attachment -- thin wrapper over upload_service.read_upload_bytes() that
    also recovers the filename, since email attachments need one."""
    content = read_upload_bytes(case.photo_url)
    if content is None:
        return None
    filename = case.photo_url.rsplit("/media/", 1)[-1]
    return filename, content


def _sender_local_part(actor: User) -> str:
    """A stable, human-readable, collision-safe local-part for
    sender_address_for(), e.g. "belagavi-city-police-4f3a2c1e" for an
    authority named "Belagavi City Police" -- same every time for the same
    account (deterministic from org_name/full_name + user id), unique across
    accounts even if two stations share a display name."""
    source = actor.org_name or actor.full_name or "authority"
    slug = re.sub(r"[^a-z0-9]+", "-", source.lower()).strip("-") or "authority"
    return f"{slug}-{actor.id.hex[:8]}"


def share_case(db: Session, case: Case, payload: CaseShareRequest, actor: User) -> None:
    """Emails the case's full details -- plus the case photo as a soft copy,
    when one exists -- to another police/NGO authority, and includes a
    direct link so the recipient can open the case on the website. Either an
    existing authority account (to_authority_id) or an arbitrary address for
    a station not yet on the platform (to_email) works; exactly one must be
    given (validated below).

    Restricted to the case's assigned authority or an admin -- sharing is
    part of an active investigation being coordinated, not something any
    authority can do to any case."""
    is_admin = actor.role == UserRole.ADMIN
    is_assigned_authority = (
        actor.role == UserRole.AUTHORITY and case.assigned_authority_id == actor.id
    )
    if not (is_admin or is_assigned_authority):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned authority or an admin can share this case",
        )

    if payload.to_authority_id is not None and payload.to_email is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either to_authority_id or to_email, not both.",
        )

    if payload.to_authority_id is not None:
        recipient = db.get(User, payload.to_authority_id)
        if recipient is None or recipient.role != UserRole.AUTHORITY or not recipient.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That recipient isn't a valid, verified authority account.",
            )
        to_email = recipient.email
    elif payload.to_email is not None:
        to_email = payload.to_email
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either to_authority_id or to_email.",
        )

    case_url = f"{settings.FRONTEND_URL.rstrip('/')}/cases/{case.id}"
    lines = [
        f"{actor.full_name}" + (f" ({actor.org_name})" if actor.org_name else ""),
        "has shared a missing person case with you on the Reunification Network.",
        "",
        f"Name: {case.name}",
    ]
    if case.age_at_disappearance is not None:
        lines.append(f"Age at disappearance: {case.age_at_disappearance}")
    lines += [
        f"Status: {case.status.value.replace('_', ' ').title()}",
        f"Last seen: {case.last_seen_address}",
        f"Last seen at: {case.last_seen_at.isoformat()}",
        "",
        "Description:",
        case.description,
        "",
    ]
    if payload.message:
        lines += ["Message from the sender:", payload.message, ""]
    lines += [
        f"View the full case, sightings, and take action here: {case_url}",
        "",
        "If you don't have an account on the Reunification Network yet, you can",
        f"register a verified authority account at {settings.FRONTEND_URL.rstrip('/')}/register "
        "to access this case directly.",
    ]
    if case.photo_url:
        lines.append("\nA photo of the case is attached to this email as a soft copy.")
    body = "\n".join(lines)

    attachments = []
    photo = _load_case_photo(case)
    if photo is not None:
        attachments.append(photo)

    send_email(
        to=to_email,
        subject=f"Case shared: {case.name} — Reunification Network",
        body=body,
        attachments=attachments,
        # Visibly from the sharing authority, not a generic system/admin
        # address. from_email is the per-authority alias under YOUR
        # verified sending domain (only takes effect with a domain-verified
        # provider -- see core/email.py; on plain Gmail SMTP it's ignored
        # and SMTP_FROM_EMAIL is used instead, with just the display name
        # and Reply-To personalized).
        from_display_name=(
            f"{actor.full_name} ({actor.org_name})"
            if actor.org_name
            else actor.full_name
        ),
        from_email=sender_address_for(_sender_local_part(actor)),
        reply_to=actor.email,
    )

    db.add(
        AuditLog(
            actor_id=actor.id,
            action="case.shared",
            target_type="case",
            target_id=case.id,
            log_metadata={
                "to_authority_id": str(payload.to_authority_id) if payload.to_authority_id else None,
                "to_email": to_email,
            },
        )
    )
    db.commit()
