"""Admin-only analytics: case volume over time, resolution-time stats,
status breakdown, and geo points for a regional heatmap. All read-only,
computed from the existing cases/audit_logs tables -- nothing new is
written here."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.case import Case, CaseStatus
from app.models.sighting import Sighting
from app.services.geo_service import from_geography


def status_breakdown(db: Session) -> dict[str, int]:
    """Case count per status -- backs the overview stat strip and the
    status-mix chart."""
    stmt = select(Case.status, func.count()).group_by(Case.status)
    counts = {status.value: 0 for status in CaseStatus}
    for status_value, count in db.execute(stmt):
        counts[status_value.value] = count
    return counts


def resolution_time_stats(db: Session) -> dict:
    """Average/median days from a case being filed to being marked
    resolved. Resolution time comes from the audit log (the timestamp of
    the case.status_changed entry whose "to" was "resolved"), not
    case.updated_at -- updated_at gets bumped by any later edit, so it
    doesn't reliably mean "when this was resolved" the way the audit trail
    does.
    """
    resolved_at = func.min(AuditLog.created_at)  # first time it was marked resolved
    days_expr = (func.extract("epoch", resolved_at - Case.created_at) / 86400.0).label("days")

    # One row per resolved case (its days-to-resolve) -- deliberately just
    # this one aggregate (min) per group here; avg/median happen in the
    # outer query below, since Postgres can't nest one aggregate directly
    # inside another (avg(min(...)) in a single query is invalid SQL).
    per_case = (
        select(days_expr)
        .select_from(Case)
        .join(
            AuditLog,
            (AuditLog.target_id == Case.id)
            & (AuditLog.target_type == "case")
            & (AuditLog.action == "case.status_changed")
            & (AuditLog.log_metadata.op("->>")("to") == "resolved"),
        )
        .group_by(Case.id, Case.created_at)
        .subquery()
    )

    outer = select(
        func.count(),
        func.avg(per_case.c.days),
        func.percentile_cont(0.5).within_group(per_case.c.days),
    )
    count, avg_days, median_days = db.execute(outer).one()
    return {
        "resolved_case_count": count or 0,
        "avg_days_to_resolve": round(avg_days, 1) if avg_days is not None else None,
        "median_days_to_resolve": round(median_days, 1) if median_days is not None else None,
    }


def case_volume_by_week(db: Session, weeks: int = 12) -> list[dict]:
    """Cases filed per week, most recent `weeks` weeks, oldest first --
    backs the volume-over-time chart. Weeks with zero cases are included
    (not just skipped), so the chart doesn't visually imply a gap is a
    missing data point rather than a genuine quiet week."""
    period = func.date_trunc("week", Case.created_at)
    stmt = (
        select(period.label("period_start"), func.count())
        .where(Case.created_at >= func.now() - func.make_interval(0, 0, 0, weeks * 7))
        .group_by(period)
        .order_by(period)
    )
    rows = {row.period_start.date(): row[1] for row in db.execute(stmt)}

    # Fill any zero-count weeks the query above has no row for.
    from datetime import date, timedelta

    today = date.today()
    this_week_start = today - timedelta(days=today.weekday())
    result = []
    for i in range(weeks - 1, -1, -1):
        week_start = this_week_start - timedelta(weeks=i)
        result.append({"period_start": week_start.isoformat(), "count": rows.get(week_start, 0)})
    return result


def heatmap_points(db: Session, limit: int = 3000) -> list[dict]:
    """(lat, lng, status) for every case with a last-seen location -- feeds
    the admin regional map. Capped at `limit` for response size; a real
    deployment with more cases than that would want server-side clustering,
    which is out of scope here."""
    stmt = select(Case.last_seen_location, Case.status).limit(limit)
    points = []
    for location, status_value in db.execute(stmt):
        point = from_geography(location)
        if point is not None:
            points.append({"lat": point.lat, "lng": point.lng, "status": status_value.value})
    return points


def sighting_totals(db: Session) -> dict:
    """Total/verified/pending/dismissed sighting counts -- a small
    supporting stat for the overview strip."""
    stmt = select(Sighting.status, func.count()).group_by(Sighting.status)
    counts = {"pending": 0, "verified": 0, "dismissed": 0}
    for status_value, count in db.execute(stmt):
        counts[status_value.value] = count
    counts["total"] = sum(counts.values())
    return counts
