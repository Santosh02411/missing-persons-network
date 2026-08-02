from app.models.user import UserRole


def _login(client, email, password):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()


# ---------------------------------------------------------------------------
# Multi-device sessions
# ---------------------------------------------------------------------------


def test_second_login_does_not_invalidate_first_session(client, make_user):
    user = make_user(role=UserRole.REPORTER)
    session_a = _login(client, user.email, "testpassword123")
    session_b = _login(client, user.email, "testpassword123")

    refresh_a = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": session_a["refresh_token"]}
    )
    refresh_b = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": session_b["refresh_token"]}
    )
    assert refresh_a.status_code == 200
    assert refresh_b.status_code == 200


def test_logout_only_revokes_current_session(client, make_user):
    user = make_user(role=UserRole.REPORTER)
    session_a = _login(client, user.email, "testpassword123")
    session_b = _login(client, user.email, "testpassword123")

    client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {session_a['access_token']}"},
    )

    refresh_a = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": session_a["refresh_token"]}
    )
    refresh_b = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": session_b["refresh_token"]}
    )
    assert refresh_a.status_code == 401
    assert refresh_b.status_code == 200


def test_logout_all_revokes_every_session(client, make_user):
    user = make_user(role=UserRole.REPORTER)
    session_a = _login(client, user.email, "testpassword123")
    session_b = _login(client, user.email, "testpassword123")

    client.post(
        "/api/v1/auth/logout-all",
        headers={"Authorization": f"Bearer {session_a['access_token']}"},
    )

    for session in (session_a, session_b):
        response = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]}
        )
        assert response.status_code == 401


def test_sessions_endpoint_lists_active_sessions(client, make_user):
    user = make_user(role=UserRole.REPORTER)
    session_a = _login(client, user.email, "testpassword123")
    _login(client, user.email, "testpassword123")

    response = client.get(
        "/api/v1/auth/sessions",
        headers={"Authorization": f"Bearer {session_a['access_token']}"},
    )
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_delete_session_revokes_it(client, make_user):
    user = make_user(role=UserRole.REPORTER)
    session_a = _login(client, user.email, "testpassword123")
    headers_a = {"Authorization": f"Bearer {session_a['access_token']}"}

    sessions = client.get("/api/v1/auth/sessions", headers=headers_a).json()
    session_id = sessions[0]["session_id"]

    delete_response = client.delete(f"/api/v1/auth/sessions/{session_id}", headers=headers_a)
    assert delete_response.status_code == 204

    refresh_response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": session_a["refresh_token"]}
    )
    assert refresh_response.status_code == 401


# ---------------------------------------------------------------------------
# Admin: deactivate/reactivate accounts
# ---------------------------------------------------------------------------


def test_deactivated_user_cannot_authenticate(client, make_user, auth_headers):
    admin = make_user(role=UserRole.ADMIN)
    target = make_user(role=UserRole.REPORTER)

    response = client.post(
        f"/api/v1/admin/users/{target.id}/deactivate", headers=auth_headers(admin)
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    login_response = client.post(
        "/api/v1/auth/login", json={"email": target.email, "password": "testpassword123"}
    )
    assert login_response.status_code == 403


def test_deactivate_kills_existing_sessions_immediately(client, make_user, auth_headers):
    admin = make_user(role=UserRole.ADMIN)
    target = make_user(role=UserRole.REPORTER)
    session = _login(client, target.email, "testpassword123")

    client.post(f"/api/v1/admin/users/{target.id}/deactivate", headers=auth_headers(admin))

    refresh_response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]}
    )
    assert refresh_response.status_code == 401


def test_admin_cannot_deactivate_own_account(client, make_user, auth_headers):
    admin = make_user(role=UserRole.ADMIN)
    response = client.post(
        f"/api/v1/admin/users/{admin.id}/deactivate", headers=auth_headers(admin)
    )
    assert response.status_code == 400


def test_reactivate_restores_login(client, make_user, auth_headers):
    admin = make_user(role=UserRole.ADMIN)
    target = make_user(role=UserRole.REPORTER)
    client.post(f"/api/v1/admin/users/{target.id}/deactivate", headers=auth_headers(admin))

    reactivate_response = client.post(
        f"/api/v1/admin/users/{target.id}/reactivate", headers=auth_headers(admin)
    )
    assert reactivate_response.status_code == 200
    assert reactivate_response.json()["is_active"] is True

    login_response = client.post(
        "/api/v1/auth/login", json={"email": target.email, "password": "testpassword123"}
    )
    assert login_response.status_code == 200


def test_deactivate_requires_admin(client, make_user, auth_headers):
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    target = make_user(role=UserRole.REPORTER)
    response = client.post(
        f"/api/v1/admin/users/{target.id}/deactivate", headers=auth_headers(authority)
    )
    assert response.status_code == 403


def test_list_users_requires_admin(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    response = client.get("/api/v1/admin/users", headers=auth_headers(reporter))
    assert response.status_code == 403


def test_list_users_filters_by_role(client, make_user, auth_headers):
    admin = make_user(role=UserRole.ADMIN)
    make_user(role=UserRole.REPORTER)
    make_user(role=UserRole.AUTHORITY, is_verified=True)

    response = client.get(
        "/api/v1/admin/users", params={"role": "authority"}, headers=auth_headers(admin)
    )
    assert response.status_code == 200
    assert all(u["role"] == "authority" for u in response.json())


# ---------------------------------------------------------------------------
# Two-factor auth (TOTP)
# ---------------------------------------------------------------------------


def test_2fa_setup_requires_authority_or_admin_role(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    response = client.post("/api/v1/auth/2fa/setup", headers=auth_headers(reporter))
    assert response.status_code == 403


def test_2fa_full_setup_and_login_flow(client, make_user, auth_headers):
    import pyotp

    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    headers = auth_headers(authority)

    setup_response = client.post("/api/v1/auth/2fa/setup", headers=headers)
    assert setup_response.status_code == 200
    secret = setup_response.json()["secret"]

    valid_code = pyotp.TOTP(secret).now()
    verify_response = client.post(
        "/api/v1/auth/2fa/verify", json={"code": valid_code}, headers=headers
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["totp_enabled"] is True

    # Plain login now requires the second factor.
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": authority.email, "password": "testpassword123"},
    )
    assert login_response.status_code == 200
    login_body = login_response.json()
    assert login_body["mfa_required"] is True
    assert login_body["access_token"] is None

    completed_login = client.post(
        "/api/v1/auth/2fa/login",
        json={"mfa_token": login_body["mfa_token"], "code": pyotp.TOTP(secret).now()},
    )
    assert completed_login.status_code == 200
    assert completed_login.json()["access_token"] is not None


def test_2fa_login_rejects_wrong_code(client, make_user, auth_headers):
    import pyotp

    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    headers = auth_headers(authority)
    secret = client.post("/api/v1/auth/2fa/setup", headers=headers).json()["secret"]
    client.post("/api/v1/auth/2fa/verify", json={"code": pyotp.TOTP(secret).now()}, headers=headers)

    login_body = client.post(
        "/api/v1/auth/login",
        json={"email": authority.email, "password": "testpassword123"},
    ).json()

    response = client.post(
        "/api/v1/auth/2fa/login",
        json={"mfa_token": login_body["mfa_token"], "code": "000000"},
    )
    assert response.status_code == 401


def test_2fa_disable_requires_correct_code(client, make_user, auth_headers):
    import pyotp

    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    headers = auth_headers(authority)
    secret = client.post("/api/v1/auth/2fa/setup", headers=headers).json()["secret"]
    client.post("/api/v1/auth/2fa/verify", json={"code": pyotp.TOTP(secret).now()}, headers=headers)

    wrong_attempt = client.post(
        "/api/v1/auth/2fa/disable", json={"code": "000000"}, headers=headers
    )
    assert wrong_attempt.status_code == 400

    correct_attempt = client.post(
        "/api/v1/auth/2fa/disable", json={"code": pyotp.TOTP(secret).now()}, headers=headers
    )
    assert correct_attempt.status_code == 200
    assert correct_attempt.json()["totp_enabled"] is False
