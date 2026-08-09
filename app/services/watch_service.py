import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import send_email
from app.models.case import Case
from app.models.case_watch import CaseWatch
from app.models.user import User

logger = logging.getLogger("app.watch")


def is_watching(db: Session, case_id, user_id) -> bool:
    stmt = select(CaseWatch).where(CaseWatch.case_id == case_id, CaseWatch.user_id == user_id)
    return db.scalars(stmt).first() is not None


def watch_case(db: Session, case: Case, user: User) -> None:
    if is_watching(db, case.id, user.id):
        return  # already watching -- idempotent, not an error
    db.add(CaseWatch(user_id=user.id, case_id=case.id))
    db.commit()


def unwatch_case(db: Session, case: Case, user: User) -> None:
    stmt = select(CaseWatch).where(CaseWatch.case_id == case.id, CaseWatch.user_id == user.id)
    watch = db.scalars(stmt).first()
    if watch is None:
        return  # not watching -- idempotent, not an error
    db.delete(watch)
    db.commit()


def list_watched_cases(db: Session, user_id) -> list[Case]:
    """Backs the citizen dashboard's "cases I'm watching" section."""
    stmt = (
        select(Case)
        .join(CaseWatch, CaseWatch.case_id == Case.id)
        .where(CaseWatch.user_id == user_id)
        .order_by(Case.updated_at.desc())
    )
    return list(db.scalars(stmt))


def notify_watchers(db: Session, case: Case, headline: str, detail: str, exclude_user_id=None) -> None:
    """Emails everyone watching this case about an update -- called from
    case_service (status changes) and sighting_service (a sighting gets
    verified). Best-effort: an email failure for one watcher is logged and
    skipped, never raised, so it can't block the status change or review
    action that triggered it. exclude_user_id skips notifying whoever just
    made the change themselves (e.g. the authority who updated the status),
    even if they happen to also be watching their own case.
    """
    stmt = (
        select(User)
        .join(CaseWatch, CaseWatch.user_id == User.id)
        .where(CaseWatch.case_id == case.id, User.is_active.is_(True))
    )
    watchers = list(db.scalars(stmt))
    if exclude_user_id is not None:
        watchers = [w for w in watchers if w.id != exclude_user_id]
    if not watchers:
        return

    case_url = f"{settings.FRONTEND_URL.rstrip('/')}/cases/{case.id}"
    body = (
        f"{headline}\n\n"
        f"Case: {case.name}\n"
        f"{detail}\n\n"
        f"View the case: {case_url}\n\n"
        "You're getting this because you're watching this case on the "
        "Reunification Network. You can stop watching it any time from the "
        "case page."
    )
    for watcher in watchers:
        try:
            send_email(
                to=watcher.email,
                subject=f"Update on a case you're watching: {case.name}",
                body=body,
            )
        except Exception:
            logger.exception(
                "Failed to notify watcher %s for case %s", watcher.id, case.id
            )
