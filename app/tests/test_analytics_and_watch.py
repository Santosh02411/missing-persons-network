from unittest.mock import patch

from app.models.user import UserRole
from app.services import analytics_service

CASE_PAYLOAD = {
    "name": "Jane Doe",
    "description": "Last seen near the central market wearing a blue jacket.",
    "last_seen_location": {"lat": 15.8497, "lng": 74.4977},
    "last_seen_address": "Central Market, Belagavi",
    "last_seen_at": "2026-07-01T10:00:00Z",
}


def _create_case(client, headers, **overrides) -> dict:
    payload = {**CASE_PAYLOAD, **overrides}
    response = client.post("/api/v1/cases", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------- analytics


def test_analytics_requires_admin(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)

    for headers in (auth_headers(reporter), auth_headers(authority)):
        assert client.get("/api/v1/admin/analytics/overview", headers=headers).status_code == 403
        assert client.get("/api/v1/admin/analytics/volume", headers=headers).status_code == 403
        assert client.get("/api/v1/admin/analytics/heatmap", headers=headers).status_code == 403


def test_analytics_overview_reflects_case_status(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    admin = make_user(role=UserRole.ADMIN, is_verified=True)

    case = _create_case(client, auth_headers(reporter))
    client.post(f"/api/v1/cases/{case['id']}/approve", headers=auth_headers(authority))

    response = client.get("/api/v1/admin/analytics/overview", headers=auth_headers(admin))
    assert response.status_code == 200
    body = response.json()
    assert body["total_cases"] >= 1
    assert body["status_breakdown"]["open"] >= 1


def test_resolution_time_stats_computed_from_audit_log(client, make_user, auth_headers, db_session):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)

    case = _create_case(client, auth_headers(reporter))
    client.post(f"/api/v1/cases/{case['id']}/approve", headers=auth_headers(authority))
    response = client.patch(
        f"/api/v1/cases/{case['id']}/status",
        json={"status": "resolved"},
        headers=auth_headers(authority),
    )
    assert response.status_code == 200

    stats = analytics_service.resolution_time_stats(db_session)
    assert stats["resolved_case_count"] >= 1
    # Resolved essentially instantly in this test, so days-to-resolve should
    # be a small non-negative number, not None and not something absurd.
    assert stats["avg_days_to_resolve"] is not None
    assert 0 <= stats["avg_days_to_resolve"] < 1
    assert 0 <= stats["median_days_to_resolve"] < 1


def test_case_volume_by_week_includes_this_week(client, make_user, auth_headers, db_session):
    reporter = make_user(role=UserRole.REPORTER)
    _create_case(client, auth_headers(reporter))

    weeks = analytics_service.case_volume_by_week(db_session, weeks=4)
    assert len(weeks) == 4
    assert sum(w["count"] for w in weeks) >= 1
    assert weeks[-1]["count"] >= 1  # most recent week (this one) has the case we just filed


def test_heatmap_points_returns_coordinates(client, make_user, auth_headers, db_session):
    reporter = make_user(role=UserRole.REPORTER)
    _create_case(client, auth_headers(reporter))

    points = analytics_service.heatmap_points(db_session)
    assert len(points) >= 1
    assert any(abs(p["lat"] - 15.8497) < 0.01 and abs(p["lng"] - 74.4977) < 0.01 for p in points)


# -------------------------------------------------------------- case watch


def test_reporter_auto_watches_own_filed_case(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    case = _create_case(client, auth_headers(reporter))

    response = client.get(f"/api/v1/cases/{case['id']}/watch", headers=auth_headers(reporter))
    assert response.status_code == 200
    assert response.json()["is_watching"] is True


def test_watch_and_unwatch_are_idempotent(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    other = make_user(role=UserRole.REPORTER)
    case = _create_case(client, auth_headers(reporter))
    client.post(f"/api/v1/cases/{case['id']}/approve", headers=auth_headers(authority))

    # `other` didn't file it, so starts out not watching.
    assert client.get(f"/api/v1/cases/{case['id']}/watch", headers=auth_headers(other)).json()["is_watching"] is False

    assert client.post(f"/api/v1/cases/{case['id']}/watch", headers=auth_headers(other)).status_code == 204
    assert client.post(f"/api/v1/cases/{case['id']}/watch", headers=auth_headers(other)).status_code == 204  # idempotent
    assert client.get(f"/api/v1/cases/{case['id']}/watch", headers=auth_headers(other)).json()["is_watching"] is True

    assert client.delete(f"/api/v1/cases/{case['id']}/watch", headers=auth_headers(other)).status_code == 204
    assert client.delete(f"/api/v1/cases/{case['id']}/watch", headers=auth_headers(other)).status_code == 204  # idempotent
    assert client.get(f"/api/v1/cases/{case['id']}/watch", headers=auth_headers(other)).json()["is_watching"] is False


def test_watched_cases_list(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    watcher = make_user(role=UserRole.REPORTER)
    case = _create_case(client, auth_headers(reporter))
    client.post(f"/api/v1/cases/{case['id']}/approve", headers=auth_headers(authority))

    client.post(f"/api/v1/cases/{case['id']}/watch", headers=auth_headers(watcher))
    response = client.get("/api/v1/cases/watched", headers=auth_headers(watcher))
    assert response.status_code == 200
    assert case["id"] in [c["id"] for c in response.json()]


def test_watchers_notified_on_status_change_excluding_actor(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)  # auto-watches on filing
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)  # will act, and also watches
    case = _create_case(client, auth_headers(reporter))

    with patch("app.services.watch_service.send_email") as mock_send:
        client.post(f"/api/v1/cases/{case['id']}/approve", headers=auth_headers(authority))
        # approver isn't watching, so exactly the reporter gets notified
        assert mock_send.call_count == 1
        assert mock_send.call_args.kwargs["to"] == reporter.email

    with patch("app.services.watch_service.send_email") as mock_send:
        client.post(f"/api/v1/cases/{case['id']}/watch", headers=auth_headers(authority))
        client.patch(
            f"/api/v1/cases/{case['id']}/status",
            json={"status": "resolved"},
            headers=auth_headers(authority),
        )
        # authority made the change and is excluded from its own notification
        recipients = {c.kwargs["to"] for c in mock_send.call_args_list}
        assert recipients == {reporter.email}


def test_no_notification_when_nobody_is_watching(client, make_user, auth_headers):
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    # A case filed by an authority itself has no separate watcher once we
    # exclude the actor -- reporter isn't used here on purpose.
    case_payload = {**CASE_PAYLOAD, "target_authority_id": str(authority.id)}
    response = client.post("/api/v1/cases", json=case_payload, headers=auth_headers(authority))
    case = response.json()

    with patch("app.services.watch_service.send_email") as mock_send:
        client.post(f"/api/v1/cases/{case['id']}/approve", headers=auth_headers(authority))
        mock_send.assert_not_called()
