"""Duplicate-case detection: at filing time, flags other cases that look
similar by name, last-seen location, and last-seen date, for the reviewing
authority to see -- and lets the frontend show the reporter a "this might
already be filed" warning before they submit, which they can still
dismiss and file anyway.

Deliberately never blocks filing. A missing-persons registry that refused
or delayed a genuine report because it resembled an existing one would be
actively dangerous -- two different people can share a name, and the same
person can legitimately have more than one open report from different
families/witnesses. This is a helper signal for a human to weigh, not a
gate.
"""
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.case import Case, CaseStatus
from app.schemas.geo import GeoPoint
from app.services.geo_service import _geography_point, from_geography

# Candidate cases are pre-filtered in SQL by location + date proximity
# (cheap, indexed), then scored by name similarity in Python (SequenceMatcher
# has no useful SQL equivalent here) -- keeps this fast even with many cases,
# since only genuinely nearby-in-place-and-time cases are ever compared by name.
CANDIDATE_RADIUS_KM = 50
CANDIDATE_DATE_WINDOW_DAYS = 14
NAME_SIMILARITY_THRESHOLD = 0.6


def _normalize_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize_name(a), _normalize_name(b)).ratio()


def find_possible_duplicates(
    db: Session,
    name: str,
    last_seen_location: GeoPoint,
    last_seen_at: datetime,
    age_at_disappearance: int | None = None,
    exclude_case_id=None,
) -> list[dict]:
    """Returns possible-duplicate matches, highest similarity first. Each
    match: {case_id, name, status, similarity, distance_km}. Only compares
    against non-dismissed cases -- a case that was reviewed and rejected as
    invalid isn't useful context for "is this already filed"."""
    point = _geography_point(last_seen_location)
    radius_m = CANDIDATE_RADIUS_KM * 1000
    window = timedelta(days=CANDIDATE_DATE_WINDOW_DAYS)

    stmt = select(Case).where(
        Case.status != CaseStatus.DISMISSED,
        func.ST_DWithin(Case.last_seen_location, point, radius_m),
        Case.last_seen_at.between(last_seen_at - window, last_seen_at + window),
    )
    if exclude_case_id is not None:
        stmt = stmt.where(Case.id != exclude_case_id)

    matches = []
    for candidate in db.scalars(stmt):
        similarity = _name_similarity(name, candidate.name)
        if similarity < NAME_SIMILARITY_THRESHOLD:
            continue
        if (
            age_at_disappearance is not None
            and candidate.age_at_disappearance is not None
            and abs(age_at_disappearance - candidate.age_at_disappearance) > 3
        ):
            continue  # ages too far apart to plausibly be the same report, even with a name match

        candidate_point = from_geography(candidate.last_seen_location)
        distance_km = None
        if candidate_point is not None:
            distance_km = _haversine_km(last_seen_location, candidate_point)

        matches.append(
            {
                "case_id": str(candidate.id),
                "name": candidate.name,
                "status": candidate.status.value,
                "similarity": round(similarity, 2),
                "distance_km": round(distance_km, 1) if distance_km is not None else None,
            }
        )

    matches.sort(key=lambda m: m["similarity"], reverse=True)
    return matches[:10]  # a form-filling reporter or a review queue only needs the closest few


def _haversine_km(a: GeoPoint, b: GeoPoint) -> float:
    import math

    lat1, lng1, lat2, lng2 = map(math.radians, [a.lat, a.lng, b.lat, b.lng])
    dlat, dlng = lat2 - lat1, lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))
