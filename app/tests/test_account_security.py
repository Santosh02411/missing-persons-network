from app.core.redis_client import redis_client
from app.models.user import UserRole


def _register_payload(**overrides) -> dict:
    payload = {
        "email": "security-test@example.com",
        "password": "supersecret123",
        "full_name": "Security Test User",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


def test_register_sends_verification_token_and_starts_unverified(client):
    response = client.post("/api/v1/auth/register", json=_register_payload())
    assert response.status_code == 201
    assert response.json()["email_verified"] is False

    # A token should now exist in Redis for this user (send_email itself just
    # logs -- we can't intercept an actual email, but the token being stored
    # is the part that matters for the verify-email endpoint to work).
    keys = list(redis_client.scan_iter("email_verify:*"))
    assert len(keys) == 1


def test_verify_email_with_valid_token_marks_verified(client):
    client.post("/api/v1/auth/register", json=_register_payload())
    token = list(redis_client.scan_iter("email_verify:*"))[0].split(":", 1)[1]

    response = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert response.status_code == 200
    assert response.json()["email_verified"] is True


def test_verify_email_with_invalid_token_400s(client):
    response = client.post("/api/v1/auth/verify-email", json={"token": "not-a-real-token"})
    assert response.status_code == 400


def test_verify_email_token_is_single_use(client):
    client.post("/api/v1/auth/register", json=_register_payload())
    token = list(redis_client.scan_iter("email_verify:*"))[0].split(":", 1)[1]

    first = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert first.status_code == 200
    second = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert second.status_code == 400


def test_resend_verification_requires_auth(client):
    response = client.post("/api/v1/auth/resend-verification")
    assert response.status_code == 401


def test_resend_verification_issues_a_new_token(client, make_user, auth_headers):
    user = make_user(role=UserRole.REPORTER)
    response = client.post("/api/v1/auth/resend-verification", headers=auth_headers(user))
    assert response.status_code == 204
    keys = list(redis_client.scan_iter("email_verify:*"))
    assert len(keys) == 1


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


def test_forgot_password_always_returns_generic_success(client, make_user):
    # Existing account
    user = make_user(role=UserRole.REPORTER)
    response = client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    assert response.status_code == 202

    # Nonexistent account -- same response shape, no enumeration signal
    response = client.post(
        "/api/v1/auth/forgot-password", json={"email": "nobody@example.com"}
    )
    assert response.status_code == 202


def test_forgot_password_only_issues_token_for_real_accounts(client, make_user):
    user = make_user(role=UserRole.REPORTER)
    client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})

    keys = list(redis_client.scan_iter("pwd_reset:*"))
    assert len(keys) == 1


def test_reset_password_with_valid_token_changes_password_and_revokes_session(
    client, make_user, auth_headers
):
    user = make_user(role=UserRole.REPORTER)
    login = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "testpassword123"}
    ).json()

    client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    token = list(redis_client.scan_iter("pwd_reset:*"))[0].split(":", 1)[1]

    reset_response = client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "newpassword456"}
    )
    assert reset_response.status_code == 200

    # Old refresh token should no longer work -- reset revokes the session.
    refresh_response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}
    )
    assert refresh_response.status_code == 401

    # New password logs in; old one doesn't.
    old_login = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "testpassword123"}
    )
    assert old_login.status_code == 401
    new_login = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "newpassword456"}
    )
    assert new_login.status_code == 200


def test_reset_password_with_invalid_token_400s(client):
    response = client.post(
        "/api/v1/auth/reset-password", json={"token": "bogus", "new_password": "newpassword456"}
    )
    assert response.status_code == 400


def test_reset_password_token_is_single_use(client, make_user):
    user = make_user(role=UserRole.REPORTER)
    client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    token = list(redis_client.scan_iter("pwd_reset:*"))[0].split(":", 1)[1]

    first = client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "newpassword456"}
    )
    assert first.status_code == 200
    second = client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "anotherpass789"}
    )
    assert second.status_code == 400


# ---------------------------------------------------------------------------
# Login lockout
# ---------------------------------------------------------------------------


def test_login_locks_out_after_repeated_failures(client, make_user, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "LOGIN_FAILURE_THRESHOLD", 3)

    user = make_user(role=UserRole.REPORTER)

    for _ in range(3):
        response = client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": "wrongpassword"}
        )
        assert response.status_code == 401

    locked_response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "testpassword123"}
    )
    assert locked_response.status_code == 429
    assert "Retry-After" in locked_response.headers


def test_successful_login_clears_failure_count(client, make_user, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "LOGIN_FAILURE_THRESHOLD", 3)

    user = make_user(role=UserRole.REPORTER)

    client.post("/api/v1/auth/login", json={"email": user.email, "password": "wrongpassword"})
    client.post("/api/v1/auth/login", json={"email": user.email, "password": "wrongpassword"})

    success = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "testpassword123"}
    )
    assert success.status_code == 200

    # Failure count reset -- two more wrong attempts shouldn't trip the
    # (threshold=3) lock, since the earlier two were cleared by the success.
    client.post("/api/v1/auth/login", json={"email": user.email, "password": "wrongpassword"})
    still_open = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "wrongpassword"}
    )
    assert still_open.status_code == 401  # not 429 -- not locked yet
