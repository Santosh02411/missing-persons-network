from app.models.user import UserRole


def _register_payload(**overrides) -> dict:
    payload = {
        "email": "newuser@example.com",
        "password": "supersecret123",
        "full_name": "New Reporter",
    }
    payload.update(overrides)
    return payload


def test_register_creates_reporter_verified_by_default(client):
    response = client.post("/api/v1/auth/register", json=_register_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "reporter"
    assert body["is_verified"] is True  # reporters don't need approval


def test_register_authority_starts_unverified(client):
    payload = _register_payload(
        email="authority@example.com", role="authority", org_name="City Police"
    )
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "authority"
    assert body["is_verified"] is False  # must be approved by an admin


def test_register_cannot_self_grant_admin_role(client):
    """Regression test: role is a Literal["reporter", "authority"] in
    UserCreate specifically so this can never succeed -- admin has no
    verification gate of its own, so accepting role="admin" here would be a
    straight privilege-escalation hole. See schemas/user.py."""
    payload = _register_payload(email="wannabe-admin@example.com", role="admin")
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


def test_register_duplicate_email_conflicts(client):
    client.post("/api/v1/auth/register", json=_register_payload())
    response = client.post("/api/v1/auth/register", json=_register_payload())
    assert response.status_code == 409


def test_login_with_correct_credentials(client):
    client.post("/api/v1/auth/register", json=_register_payload())
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "newuser@example.com", "password": "supersecret123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_login_with_wrong_password_rejected(client):
    client.post("/api/v1/auth/register", json=_register_payload())
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "newuser@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_refresh_rotates_token_and_invalidates_old_one(client):
    client.post("/api/v1/auth/register", json=_register_payload())
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "newuser@example.com", "password": "supersecret123"},
    ).json()
    old_refresh_token = login["refresh_token"]

    first_refresh = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh_token}
    )
    assert first_refresh.status_code == 200
    assert first_refresh.json()["refresh_token"] != old_refresh_token

    # Reusing the now-rotated-out token must fail -- this is the token-theft
    # detection behavior, not just "expired token" handling.
    reuse_attempt = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh_token}
    )
    assert reuse_attempt.status_code == 401


def test_logout_revokes_refresh_token(client, make_user, auth_headers):
    user = make_user(role=UserRole.REPORTER)
    login = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "testpassword123"}
    ).json()

    logout_response = client.post("/api/v1/auth/logout", headers=auth_headers(user))
    assert logout_response.status_code == 204

    refresh_after_logout = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}
    )
    assert refresh_after_logout.status_code == 401


def test_protected_endpoint_rejects_missing_token(client):
    response = client.post(
        "/api/v1/cases",
        json={
            "name": "Jane Doe",
            "description": "Last seen near the market",
            "last_seen_location": {"lat": 15.85, "lng": 74.5},
            "last_seen_address": "Belagavi market",
            "last_seen_at": "2026-07-01T10:00:00Z",
        },
    )
    assert response.status_code == 401
