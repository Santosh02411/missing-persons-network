from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.models.case import CaseStatus
from app.models.user import UserRole
from app.schemas.case import CaseCreate, CaseUpdate
from app.schemas.geo import GeoPoint
from app.services import case_service


def _case_create_payload(**overrides) -> CaseCreate:
    defaults = dict(
        name="Jane Doe",
        age_at_disappearance=24,
        photo_url=None,
        description="Last seen near the market.",
        last_seen_location=GeoPoint(lat=15.8497, lng=74.4977),
        last_seen_address="Central Market, Belagavi",
        last_seen_at=datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return CaseCreate(**defaults)


def test_create_case_defaults_to_open_status(db_session, make_user):
    reporter = make_user(role=UserRole.REPORTER)
    case = case_service.create_case(db_session, _case_create_payload(), reporter=reporter)
    assert case.status == CaseStatus.OPEN
    assert case.created_by == reporter.id


def test_get_case_or_404_raises_for_missing_case(db_session):
    import uuid

    with pytest.raises(HTTPException) as exc_info:
        case_service.get_case_or_404(db_session, uuid.uuid4())
    assert exc_info.value.status_code == 404


def test_update_case_rejects_non_owner(db_session, make_user):
    owner = make_user(role=UserRole.REPORTER)
    stranger = make_user(role=UserRole.REPORTER)
    case = case_service.create_case(db_session, _case_create_payload(), reporter=owner)

    with pytest.raises(HTTPException) as exc_info:
        case_service.update_case(
            db_session, case, CaseUpdate(name="New Name"), current_user=stranger
        )
    assert exc_info.value.status_code == 403


def test_claim_case_assigns_authority(db_session, make_user):
    owner = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = case_service.create_case(db_session, _case_create_payload(), reporter=owner)

    claimed = case_service.claim_case(db_session, case, actor=authority)
    assert claimed.assigned_authority_id == authority.id


def test_claim_case_rejects_reclaiming_by_another_authority(db_session, make_user):
    owner = make_user(role=UserRole.REPORTER)
    authority_a = make_user(role=UserRole.AUTHORITY, is_verified=True)
    authority_b = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = case_service.create_case(db_session, _case_create_payload(), reporter=owner)
    case_service.claim_case(db_session, case, actor=authority_a)

    with pytest.raises(HTTPException) as exc_info:
        case_service.claim_case(db_session, case, actor=authority_b)
    assert exc_info.value.status_code == 409


def test_update_case_status_requires_assigned_authority(db_session, make_user):
    owner = make_user(role=UserRole.REPORTER)
    assigned = make_user(role=UserRole.AUTHORITY, is_verified=True)
    unassigned = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = case_service.create_case(db_session, _case_create_payload(), reporter=owner)
    case_service.claim_case(db_session, case, actor=assigned)

    with pytest.raises(HTTPException) as exc_info:
        case_service.update_case_status(db_session, case, CaseStatus.LEAD_FOUND, actor=unassigned)
    assert exc_info.value.status_code == 403

    updated = case_service.update_case_status(
        db_session, case, CaseStatus.LEAD_FOUND, actor=assigned
    )
    assert updated.status == CaseStatus.LEAD_FOUND


def test_update_case_status_writes_audit_log(db_session, make_user):
    from sqlalchemy import select

    from app.models.audit_log import AuditLog

    owner = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = case_service.create_case(db_session, _case_create_payload(), reporter=owner)
    case_service.claim_case(db_session, case, actor=authority)
    case_service.update_case_status(db_session, case, CaseStatus.RESOLVED, actor=authority)

    logs = list(
        db_session.scalars(
            select(AuditLog).where(
                AuditLog.target_id == case.id, AuditLog.action == "case.status_changed"
            )
        )
    )
    assert len(logs) == 1
    assert logs[0].log_metadata == {"from": "open", "to": "resolved"}
