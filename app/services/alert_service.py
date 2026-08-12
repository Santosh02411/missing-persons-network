"""Geofenced alerts: an opt-in, community-scale analog of an Amber Alert.
A user chooses a location and radius they care about (their home area, a
relative's neighborhood); an authority/NGO with access to a case can then
push an alert to everyone subscribed near that case's last-seen location.

Deliberately NOT automatic on every case filing -- that would be spam, and
would erode trust in the alert fast. It's a specific action an authority
takes for a case that genuinely warrants wider community attention, the
same judgment call real Amber Alerts require.
"""
import logging
import math
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import send_email
from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.user import User
from app.schemas.geo import GeoPoint
from app.services.case_service import has_case_access
from app.services.geo_service import from_geography, to_geography

logger = logging.getLogger("app.alerts")

# An authority re-pushing an alert for the same case within this window is
# almost always a mis-click or impatience, not a genuine reason to notify
# the same community twice -- this is the guard against that, not a hard
# business rule about how "alertable" news should be.
RESEND_COOLDOWN_HOURS = 24


def _haversine_km(a: GeoPoint, b: GeoPoint) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, [a.lat, a.lng, b.lat, b.lng])
    dlat, dlng = lat2 - lat1, lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def update_alert_preferences(
    db: Session, user: User, enabled: bool, location: GeoPoint | None, radius_km: float | None
) -> User:
    """Sets/updates a user's own geofenced-alert subscription. Enabling
    requires both a location and a radius -- there's nothing to match
    against otherwise; disabling can be done without touching the other
    two, so a person can pause alerts without losing their configured area."""
    if enabled and (location is None or radius_km is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set a location and radius to enable geofenced alerts.",
        )
    user.alerts_enabled = enabled
    if location is not None:
        user.alert_location = to_geography(location)
    if radius_km is not None:
        user.alert_radius_km = radius_km
    db.commit()
    db.refresh(user)
    return user


def find_nearby_subscribers(db: Session, center: GeoPoint) -> list[User]:
    """Every alerts_enabled user whose own chosen radius covers `center` --
    each subscriber's radius is theirs, not a fixed global one, so this
    compares distance per-subscriber in Python (haversine) rather than a
    single ST_DWithin call, after a cheap SQL prefilter to just
    alerts_enabled accounts with a location set."""
    stmt = select(User).where(
        User.alerts_enabled.is_(True),
        User.alert_location.isnot(None),
        User.alert_radius_km.isnot(None),
        User.is_active.is_(True),
    )
    matches = []
    for user in db.scalars(stmt):
        point = from_geography(user.alert_location)
        if point is None:
            continue
        if _haversine_km(center, point) <= user.alert_radius_km:
            matches.append(user)
    return matches


def send_geofenced_alert(db: Session, case: Case, actor: User) -> dict:
    """Pushes an alert to every subscriber near this case's last-seen
    location. Restricted to whoever has case access (assigned authority,
    a collaborator, or admin) -- this is a significant, community-facing
    action, not something any authority can trigger on any case."""
    if not has_case_access(db, case, actor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned authority, a collaborator on this case, or an admin can send an alert",
        )

    last_sent = db.scalars(
        select(AuditLog)
        .where(
            AuditLog.target_type == "case",
            AuditLog.target_id == case.id,
            AuditLog.action == "case.alert_sent",
        )
        .order_by(AuditLog.created_at.desc())
    ).first()
    if last_sent is not None:
        if datetime.now(timezone.utc) - last_sent.created_at < timedelta(hours=RESEND_COOLDOWN_HOURS):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"An alert was already sent for this case in the last {RESEND_COOLDOWN_HOURS} hours.",
            )

    center = from_geography(case.last_seen_location)
    subscribers = find_nearby_subscribers(db, center) if center else []

    case_url = f"{settings.FRONTEND_URL.rstrip('/')}/cases/{case.id}"
    body = (
        f"A missing person has been reported near an area you asked to be notified about.\n\n"
        f"Name: {case.name}\n"
        f"Last seen: {case.last_seen_address}\n"
        f"Description: {case.description}\n\n"
        f"View the case and report a sighting: {case_url}\n\n"
        "You're getting this because you opted in to geofenced alerts near this location. "
        "You can turn this off any time from your account settings."
    )
    for subscriber in subscribers:
        try:
            send_email(to=subscriber.email, subject=f"Missing person reported near you: {case.name}", body=body)
        except Exception:
            logger.exception(
                "Failed to send geofenced alert to %s for case %s", subscriber.id, case.id
            )

    db.add(
        AuditLog(
            actor_id=actor.id,
            action="case.alert_sent",
            target_type="case",
            target_id=case.id,
            log_metadata={"notified_count": len(subscribers)},
        )
    )
    db.commit()
    return {"notified_count": len(subscribers)}
