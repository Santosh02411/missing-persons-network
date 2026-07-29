from app.models.user import UserRole

CASE_PAYLOAD = {
    "name": "Jane Doe",
    "description": "Last seen near the market.",
    "last_seen_location": {"lat": 15.8497, "lng": 74.4977},
    "last_seen_address": "Central Market, Belagavi",
    "last_seen_at": "2026-07-01T10:00:00Z",
}


def test_audit_logs_requires_admin(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)

    for user in (reporter, authority):
        response = client.get("/api/v1/admin/audit-logs", headers=auth_headers(user))
        assert response.status_code == 403


def test_audit_logs_records_case_status_change(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    admin = make_user(role=UserRole.ADMIN)

    case = client.post(
        "/api/v1/cases", json=CASE_PAYLOAD, headers=auth_headers(reporter)
    ).json()
    client.post(f"/api/v1/cases/{case['id']}/claim", headers=auth_headers(authority))
    client.patch(
        f"/api/v1/cases/{case['id']}/status",
        json={"status": "resolved"},
        headers=auth_headers(authority),
    )

    response = client.get("/api/v1/admin/audit-logs", headers=auth_headers(admin))
    assert response.status_code == 200
    actions = [log["action"] for log in response.json()]
    assert "case.claimed" in actions
    assert "case.status_changed" in actions


def test_audit_logs_can_filter_by_target_type(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority_pending = make_user(role=UserRole.AUTHORITY, is_verified=False)
    admin = make_user(role=UserRole.ADMIN)

    client.post("/api/v1/cases", json=CASE_PAYLOAD, headers=auth_headers(reporter))
    client.post(
        f"/api/v1/admin/authority-requests/{authority_pending.id}/approve",
        headers=auth_headers(admin),
    )

    response = client.get(
        "/api/v1/admin/audit-logs", params={"target_type": "user"}, headers=auth_headers(admin)
    )
    assert response.status_code == 200
    logs = response.json()
    assert len(logs) == 1
    assert logs[0]["target_type"] == "user"
    assert logs[0]["action"] == "user.authority_approved"
