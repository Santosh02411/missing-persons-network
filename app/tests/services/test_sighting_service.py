from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.models.sighting import SightingStatus
from app.models.user import UserRole
from app.schemas.case import CaseCreate
from app.schemas.geo import GeoPoint
from app.schemas.sighting import SightingCreate
from app.services import case_service, sighting_service


def _make_case(db_session, reporter):
    payload = CaseCreate(
        name="Jane Doe",
        description="Last seen near the market.",
        last_seen_location=GeoPoint(lat=15.8497, lng=74.4977),
        last_seen_address="Central Market, Belagavi",
        last_seen_at=datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
    )
    return case_service.create_case(db_session, payload, reporter=reporter)


def _sighting_payload(case_id, **overrides) -> SightingCreate:
    defaults = dict(
        case_id=case_id,
        location=GeoPoint(lat=15.86, lng=74.51),
        address_text="Bus stand, Belagavi",
        description="Saw someone matching the description",
        photo_url=None,
    )
    defaults.update(overrides)
    return SightingCreate(**defaults)


def test_create_sighting_without_reporter_is_anonymous(db_session, make_user):
    reporter = make_user(role=UserRole.REPORTER)
    case = _make_case(db_session, reporter)

    sighting = sighting_service.create_sighting(
        db_session, _sighting_payload(case.id), reporter=None
    )
    assert sighting.reported_by is None
    assert sighting.status == SightingStatus.PENDING


def test_create_sighting_for_unknown_case_404s(db_session):
    import uuid

    with pytest.raises(HTTPException) as exc_info:
        sighting_service.create_sighting(
            db_session, _sighting_payload(uuid.uuid4()), reporter=None
        )
    assert exc_info.value.status_code == 404


def test_review_sighting_rejects_pending_as_outcome(db_session, make_user):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _make_case(db_session, reporter)
    sighting = sighting_service.create_sighting(db_session, _sighting_payload(case.id), reporter=None)

    with pytest.raises(HTTPException) as exc_info:
        sighting_service.review_sighting(
            db_session, sighting, SightingStatus.PENDING, reviewer=authority
        )
    assert exc_info.value.status_code == 400


def test_review_sighting_records_reviewer_and_timestamp(db_session, make_user):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _make_case(db_session, reporter)
    sighting = sighting_service.create_sighting(db_session, _sighting_payload(case.id), reporter=None)

    reviewed = sighting_service.review_sighting(
        db_session, sighting, SightingStatus.VERIFIED, reviewer=authority
    )
    assert reviewed.status == SightingStatus.VERIFIED
    assert reviewed.reviewed_by == authority.id
    assert reviewed.reviewed_at is not None


def test_list_sightings_for_case_orders_newest_first(db_session, make_user):
    reporter = make_user(role=UserRole.REPORTER)
    case = _make_case(db_session, reporter)
    first = sighting_service.create_sighting(
        db_session, _sighting_payload(case.id, description="first"), reporter=None
    )
    second = sighting_service.create_sighting(
        db_session, _sighting_payload(case.id, description="second"), reporter=None
    )

    results = sighting_service.list_sightings_for_case(db_session, case.id)
    assert [s.id for s in results][:2] == [second.id, first.id]
