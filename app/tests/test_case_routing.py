import uuid

from app.models.user import UserRole
from app.services.geo_service import to_geography
from app.schemas.geo import GeoPoint

CASE_PAYLOAD = {
    "name": "Jane Doe",
    "age_at_disappearance": 24,
    "description": "Last seen near the central market wearing a blue jacket.",
    "last_seen_location": {"lat": 15.8497, "lng": 74.4977},  # Belagavi
    "last_seen_address": "Central Market, Belagavi",
    "last_seen_at": "2026-07-01T10:00:00Z",
}

BELAGAVI = {"lat": 15.8497, "lng": 74.4977}
MUMBAI = {"lat": 19.0760, "lng": 72.8777}  # ~600km away


def _create_case(client, headers, **overrides) -> dict:
    payload = {**CASE_PAYLOAD, **overrides}
    response = client.post("/api/v1/cases", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _set_jurisdiction(db_session, user, lat, lng):
    user.jurisdiction_location = to_geography(GeoPoint(lat=lat, lng=lng))
    db_session.commit()
    db_session.refresh(user)


def test_case_auto_routes_to_nearest_authority(client, make_user, auth_headers, db_session):
    reporter = make_user(role=UserRole.REPORTER)
    near_authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    far_authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    _set_jurisdiction(db_session, near_authority, **BELAGAVI)
    _set_jurisdiction(db_session, far_authority, **MUMBAI)

    case = _create_case(client, auth_headers(reporter))
    assert case["target_authority_id"] == str(near_authority.id)


def test_case_falls_back_to_broadcast_with_no_jurisdictions_set(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    make_user(role=UserRole.AUTHORITY, is_verified=True)  # no jurisdiction set

    case = _create_case(client, auth_headers(reporter))
    assert case["target_authority_id"] is None


def test_reporter_can_choose_a_specific_station(client, make_user, auth_headers, db_session):
    reporter = make_user(role=UserRole.REPORTER)
    chosen = make_user(role=UserRole.AUTHORITY, is_verified=True)
    other = make_user(role=UserRole.AUTHORITY, is_verified=True)
    _set_jurisdiction(db_session, other, **BELAGAVI)  # nearer, but not chosen

    case = _create_case(client, auth_headers(reporter), target_authority_id=str(chosen.id))
    assert case["target_authority_id"] == str(chosen.id)


def test_cannot_choose_unverified_authority_as_station(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    unverified = make_user(role=UserRole.AUTHORITY, is_verified=False)

    payload = {**CASE_PAYLOAD, "target_authority_id": str(unverified.id)}
    response = client.post("/api/v1/cases", json=payload, headers=auth_headers(reporter))
    assert response.status_code == 400


def test_pending_queue_only_shows_routed_authority_their_cases(
    client, make_user, auth_headers, db_session
):
    reporter = make_user(role=UserRole.REPORTER)
    station_a = make_user(role=UserRole.AUTHORITY, is_verified=True)
    station_b = make_user(role=UserRole.AUTHORITY, is_verified=True)

    case = _create_case(client, auth_headers(reporter), target_authority_id=str(station_a.id))

    resp_a = client.get("/api/v1/cases/pending-approval", headers=auth_headers(station_a))
    resp_b = client.get("/api/v1/cases/pending-approval", headers=auth_headers(station_b))

    assert case["id"] in [c["id"] for c in resp_a.json()]
    assert case["id"] not in [c["id"] for c in resp_b.json()]


def test_pending_queue_includes_unrouted_cases_for_any_authority(
    client, make_user, auth_headers
):
    reporter = make_user(role=UserRole.REPORTER)
    station = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_case(client, auth_headers(reporter))  # no jurisdictions set -> unrouted

    resp = client.get("/api/v1/cases/pending-approval", headers=auth_headers(station))
    assert case["id"] in [c["id"] for c in resp.json()]


def test_only_routed_authority_can_approve_case(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    station_a = make_user(role=UserRole.AUTHORITY, is_verified=True)
    station_b = make_user(role=UserRole.AUTHORITY, is_verified=True)

    case = _create_case(client, auth_headers(reporter), target_authority_id=str(station_a.id))

    response = client.post(f"/api/v1/cases/{case['id']}/approve", headers=auth_headers(station_b))
    assert response.status_code == 403

    response = client.post(f"/api/v1/cases/{case['id']}/approve", headers=auth_headers(station_a))
    assert response.status_code == 200
    assert response.json()["status"] == "open"


def test_admin_can_approve_any_routed_case(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    station = make_user(role=UserRole.AUTHORITY, is_verified=True)
    admin = make_user(role=UserRole.ADMIN, is_verified=True)

    case = _create_case(client, auth_headers(reporter), target_authority_id=str(station.id))
    response = client.post(f"/api/v1/cases/{case['id']}/approve", headers=auth_headers(admin))
    assert response.status_code == 200


def test_share_case_requires_assigned_authority(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    approver = make_user(role=UserRole.AUTHORITY, is_verified=True)
    other_authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    recipient = make_user(role=UserRole.AUTHORITY, is_verified=True)

    case = _create_case(client, auth_headers(reporter))
    client.post(f"/api/v1/cases/{case['id']}/approve", headers=auth_headers(approver))

    response = client.post(
        f"/api/v1/cases/{case['id']}/share",
        json={"to_authority_id": str(recipient.id)},
        headers=auth_headers(other_authority),
    )
    assert response.status_code == 403

    response = client.post(
        f"/api/v1/cases/{case['id']}/share",
        json={"to_authority_id": str(recipient.id)},
        headers=auth_headers(approver),
    )
    assert response.status_code == 204


def test_share_case_by_arbitrary_email(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    approver = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_case(client, auth_headers(reporter))
    client.post(f"/api/v1/cases/{case['id']}/approve", headers=auth_headers(approver))

    response = client.post(
        f"/api/v1/cases/{case['id']}/share",
        json={"to_email": "another-station@example.com", "message": "Please take a look"},
        headers=auth_headers(approver),
    )
    assert response.status_code == 204


def test_share_case_requires_a_recipient(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    approver = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_case(client, auth_headers(reporter))
    client.post(f"/api/v1/cases/{case['id']}/approve", headers=auth_headers(approver))

    response = client.post(
        f"/api/v1/cases/{case['id']}/share", json={}, headers=auth_headers(approver)
    )
    assert response.status_code == 400


def test_nearby_authorities_endpoint(client, make_user, auth_headers, db_session):
    reporter = make_user(role=UserRole.REPORTER)
    near = make_user(role=UserRole.AUTHORITY, is_verified=True, org_name="Belagavi Police")
    far = make_user(role=UserRole.AUTHORITY, is_verified=True, org_name="Mumbai Police")
    _set_jurisdiction(db_session, near, **BELAGAVI)
    _set_jurisdiction(db_session, far, **MUMBAI)

    response = client.get(
        "/api/v1/authorities/nearby",
        params={"lat": BELAGAVI["lat"], "lng": BELAGAVI["lng"], "radius_km": 50},
        headers=auth_headers(reporter),
    )
    assert response.status_code == 200
    ids = [a["id"] for a in response.json()]
    assert str(near.id) in ids
    assert str(far.id) not in ids


def test_search_authorities_endpoint(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    make_user(role=UserRole.AUTHORITY, is_verified=True, org_name="Belagavi City Police")

    response = client.get(
        "/api/v1/authorities/search", params={"q": "Belagavi"}, headers=auth_headers(reporter)
    )
    assert response.status_code == 200
    assert any("Belagavi" in (a["org_name"] or "") for a in response.json())


def test_update_jurisdiction_requires_authority_or_admin(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    response = client.patch(
        "/api/v1/auth/me/jurisdiction",
        json={"jurisdiction_location": BELAGAVI},
        headers=auth_headers(reporter),
    )
    assert response.status_code == 403

    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    response = client.patch(
        "/api/v1/auth/me/jurisdiction",
        json={"jurisdiction_location": BELAGAVI},
        headers=auth_headers(authority),
    )
    assert response.status_code == 200
    assert response.json()["jurisdiction_location"] == BELAGAVI
