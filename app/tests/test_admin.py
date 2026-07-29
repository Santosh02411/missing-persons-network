from app.models.user import UserRole


def test_admin_endpoints_require_admin_role(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)

    for user in (reporter, authority):
        response = client.get("/api/v1/admin/authority-requests", headers=auth_headers(user))
        assert response.status_code == 403


def test_admin_can_list_and_approve_pending_authorities(client, make_user, auth_headers):
    admin = make_user(role=UserRole.ADMIN)
    pending_authority = make_user(role=UserRole.AUTHORITY, is_verified=False)

    list_response = client.get(
        "/api/v1/admin/authority-requests", headers=auth_headers(admin)
    )
    assert list_response.status_code == 200
    pending_ids = [u["id"] for u in list_response.json()]
    assert str(pending_authority.id) in pending_ids

    approve_response = client.post(
        f"/api/v1/admin/authority-requests/{pending_authority.id}/approve",
        headers=auth_headers(admin),
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["is_verified"] is True


def test_admin_endpoints_require_auth_at_all(client):
    response = client.get("/api/v1/admin/authority-requests")
    assert response.status_code == 401


def test_approving_a_non_authority_user_404s(client, make_user, auth_headers):
    admin = make_user(role=UserRole.ADMIN)
    reporter = make_user(role=UserRole.REPORTER)

    response = client.post(
        f"/api/v1/admin/authority-requests/{reporter.id}/approve",
        headers=auth_headers(admin),
    )
    assert response.status_code == 404
