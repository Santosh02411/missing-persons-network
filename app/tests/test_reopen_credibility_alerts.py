from unittest.mock import patch

from app.models.user import UserRole

CASE_PAYLOAD = {
    "name": "Jane Doe",
    "description": "Last seen near the central market wearing a blue jacket.",
    "last_seen_location": {"lat": 15.8497, "lng": 74.4977},
    "last_seen_address": "Central Market, Belagavi",
    "last_seen_at": "2026-07-01T10:00:00Z",
}


def _create_and_approve(client, reporter_headers, authority_headers) -> dict:
    response = client.post("/api/v1/cases", json=CASE_PAYLOAD, headers=reporter_headers)
    assert response.status_code == 201, response.text
    case = response.json()
    approve = client.post(f"/api/v1/cases/{case['id']}/approve", headers=authority_headers)
    assert approve.status_code == 200
    return approve.json()


def _resolve(client, case_id, authority_headers):
    r = client.patch(f"/api/v1/cases/{case_id}/status", json={"status": "resolved"}, headers=authority_headers)
    assert r.status_code == 200
    return r.json()


# --------------------------------------------------------------- reopening


def test_cannot_reopen_a_case_that_isnt_resolved(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))  # still "open"

    response = client.post(
        f"/api/v1/cases/{case['id']}/reopen", json={"reason": "test"}, headers=auth_headers(authority)
    )
    assert response.status_code == 409


def test_reopen_requires_case_access(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    other_authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))
    _resolve(client, case["id"], auth_headers(authority))

    response = client.post(
        f"/api/v1/cases/{case['id']}/reopen", json={"reason": "test"}, headers=auth_headers(other_authority)
    )
    assert response.status_code == 403


def test_reopen_requires_a_reason(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))
    _resolve(client, case["id"], auth_headers(authority))

    response = client.post(f"/api/v1/cases/{case['id']}/reopen", json={"reason": ""}, headers=auth_headers(authority))
    assert response.status_code == 422


def test_reopen_sets_status_back_to_open_and_logs_audit(client, make_user, auth_headers, db_session):
    from sqlalchemy import select

    from app.models.audit_log import AuditLog

    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))
    _resolve(client, case["id"], auth_headers(authority))

    response = client.post(
        f"/api/v1/cases/{case['id']}/reopen",
        json={"reason": "Person was seen again after being marked found in error."},
        headers=auth_headers(authority),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "open"

    log = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "case.reopened")
    ).first()
    assert log is not None
    assert str(log.target_id) == case["id"]
    assert "error" in log.log_metadata["reason"]


def test_reopened_case_appears_in_timeline(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))
    _resolve(client, case["id"], auth_headers(authority))
    client.post(f"/api/v1/cases/{case['id']}/reopen", json={"reason": "correction"}, headers=auth_headers(authority))

    response = client.get(f"/api/v1/cases/{case['id']}/timeline", headers=auth_headers(reporter))
    types = [e["type"] for e in response.json()]
    assert "case.reopened" in types


# ------------------------------------------------------- sighting credibility


def test_reporter_stats_shown_in_pending_queue(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    tipster = make_user(role=UserRole.REPORTER)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    def _report():
        r = client.post(
            "/api/v1/sightings",
            json={
                "case_id": case["id"],
                "location": {"lat": 15.86, "lng": 74.51},
                "address_text": "Bus stand",
                "description": "Saw them",
            },
            headers=auth_headers(tipster),
        )
        assert r.status_code == 201
        return r.json()["id"]

    verified_id = _report()
    dismissed_id = _report()
    pending_id = _report()

    client.patch(f"/api/v1/sightings/{verified_id}/review", json={"status": "verified"}, headers=auth_headers(authority))
    client.patch(f"/api/v1/sightings/{dismissed_id}/review", json={"status": "dismissed"}, headers=auth_headers(authority))

    response = client.get("/api/v1/sightings/pending", headers=auth_headers(authority))
    assert response.status_code == 200
    pending_item = next(s for s in response.json() if s["id"] == pending_id)
    assert pending_item["reporter_stats"] == {"verified": 1, "dismissed": 1, "pending": 1, "total": 3}


def test_reporter_stats_none_for_anonymous_or_no_history(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    fresh_tipster = make_user(role=UserRole.REPORTER)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    r = client.post(
        "/api/v1/sightings",
        json={
            "case_id": case["id"],
            "location": {"lat": 15.86, "lng": 74.51},
            "address_text": "Bus stand",
            "description": "Saw them",
        },
        headers=auth_headers(fresh_tipster),
    )
    sighting_id = r.json()["id"]

    response = client.get("/api/v1/sightings/pending", headers=auth_headers(authority))
    item = next(s for s in response.json() if s["id"] == sighting_id)
    # First-ever sighting from this reporter -- has history (itself, pending), not None
    assert item["reporter_stats"]["total"] == 1
    assert item["reporter_stats"]["pending"] == 1


def test_reporter_stats_not_exposed_on_public_case_sighting_list(client, make_user, auth_headers):
    """reporter_stats must only ever appear on the authority-facing pending
    queue (SightingQueueItem), never on the general case-detail sighting
    list anyone logged in can see."""
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    tipster = make_user(role=UserRole.REPORTER)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))
    client.post(
        "/api/v1/sightings",
        json={
            "case_id": case["id"],
            "location": {"lat": 15.86, "lng": 74.51},
            "address_text": "Bus stand",
            "description": "Saw them",
        },
        headers=auth_headers(tipster),
    )

    response = client.get(f"/api/v1/sightings/case/{case['id']}", headers=auth_headers(reporter))
    assert response.status_code == 200
    assert "reporter_stats" not in response.json()[0]


# ------------------------------------------------------------- geofenced alerts


def test_enable_alerts_requires_location_and_radius(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    response = client.patch(
        "/api/v1/auth/me/alert-preferences", json={"enabled": True}, headers=auth_headers(reporter)
    )
    assert response.status_code == 400


def test_enable_alerts_with_location_succeeds(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    response = client.patch(
        "/api/v1/auth/me/alert-preferences",
        json={"enabled": True, "location": {"lat": 15.85, "lng": 74.50}, "radius_km": 20},
        headers=auth_headers(reporter),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["alerts_enabled"] is True
    assert body["alert_radius_km"] == 20


def test_send_alert_requires_case_access(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    other_authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    response = client.post(f"/api/v1/cases/{case['id']}/alert", headers=auth_headers(other_authority))
    assert response.status_code == 403


def test_send_alert_notifies_nearby_subscribers_only(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    nearby_subscriber = make_user(role=UserRole.REPORTER)
    far_subscriber = make_user(role=UserRole.REPORTER)
    not_subscribed = make_user(role=UserRole.REPORTER)

    client.patch(
        "/api/v1/auth/me/alert-preferences",
        json={"enabled": True, "location": {"lat": 15.86, "lng": 74.51}, "radius_km": 20},
        headers=auth_headers(nearby_subscriber),
    )
    client.patch(
        "/api/v1/auth/me/alert-preferences",
        json={"enabled": True, "location": {"lat": 19.0760, "lng": 72.8777}, "radius_km": 20},  # Mumbai
        headers=auth_headers(far_subscriber),
    )

    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))  # Belagavi

    with patch("app.services.alert_service.send_email") as mock_send:
        response = client.post(f"/api/v1/cases/{case['id']}/alert", headers=auth_headers(authority))
        assert response.status_code == 200
        assert response.json()["notified_count"] == 1
        recipients = {c.kwargs["to"] for c in mock_send.call_args_list}
        assert recipients == {nearby_subscriber.email}


def test_send_alert_rate_limited_within_cooldown(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    with patch("app.services.alert_service.send_email"):
        first = client.post(f"/api/v1/cases/{case['id']}/alert", headers=auth_headers(authority))
        assert first.status_code == 200
        second = client.post(f"/api/v1/cases/{case['id']}/alert", headers=auth_headers(authority))
        assert second.status_code == 429
