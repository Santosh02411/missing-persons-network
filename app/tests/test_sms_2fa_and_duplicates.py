from unittest.mock import patch

from app.models.user import UserRole

CASE_PAYLOAD = {
    "name": "Jane Doe",
    "description": "Last seen near the central market wearing a blue jacket.",
    "last_seen_location": {"lat": 15.8497, "lng": 74.4977},
    "last_seen_address": "Central Market, Belagavi",
    "last_seen_at": "2026-07-01T10:00:00Z",
}


# ------------------------------------------------------------------ SMS 2FA


def test_sms_otp_setup_requires_authority_or_admin(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    response = client.post(
        "/api/v1/auth/2fa/sms-otp/setup",
        json={"phone_number": "+15551234567"},
        headers=auth_headers(reporter),
    )
    assert response.status_code == 403


def test_sms_otp_full_setup_and_login_flow(client, make_user, auth_headers):
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    headers = auth_headers(authority)

    with patch("app.services.auth_service.send_sms") as mock_sms:
        setup = client.post(
            "/api/v1/auth/2fa/sms-otp/setup", json={"phone_number": "+15551234567"}, headers=headers
        )
        assert setup.status_code == 202
        sent_code = mock_sms.call_args.kwargs["body"].split(": ")[1].split(".")[0]
        assert mock_sms.call_args.kwargs["to"] == "+15551234567"

    verify = client.post("/api/v1/auth/2fa/sms-otp/verify", json={"code": sent_code}, headers=headers)
    assert verify.status_code == 200
    assert verify.json()["sms_otp_enabled"] is True

    # Now log in and confirm SMS OTP is required, and a code is sent.
    with patch("app.services.auth_service.send_sms") as mock_sms:
        login = client.post(
            "/api/v1/auth/login", json={"email": authority.email, "password": "testpassword123"}
        )
        assert login.status_code == 200
        body = login.json()
        assert body["mfa_required"] is True
        assert body["mfa_method"] == "sms_otp"
        login_code = mock_sms.call_args.kwargs["body"].split(": ")[1].split(".")[0]

    complete = client.post(
        "/api/v1/auth/2fa/login", json={"mfa_token": body["mfa_token"], "code": login_code}
    )
    assert complete.status_code == 200
    assert "access_token" in complete.json()


def test_sms_otp_wrong_code_rejected(client, make_user, auth_headers):
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    headers = auth_headers(authority)
    with patch("app.services.auth_service.send_sms"):
        client.post("/api/v1/auth/2fa/sms-otp/setup", json={"phone_number": "+15551234567"}, headers=headers)
    response = client.post("/api/v1/auth/2fa/sms-otp/verify", json={"code": "000000"}, headers=headers)
    assert response.status_code == 400


def test_cannot_enable_sms_otp_and_totp_together(client, make_user, auth_headers):
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    headers = auth_headers(authority)

    setup_totp = client.post("/api/v1/auth/2fa/setup", headers=headers)
    assert setup_totp.status_code == 200
    import pyotp

    code = pyotp.TOTP(setup_totp.json()["secret"]).now()
    client.post("/api/v1/auth/2fa/verify", json={"code": code}, headers=headers)

    response = client.post(
        "/api/v1/auth/2fa/sms-otp/setup", json={"phone_number": "+15551234567"}, headers=headers
    )
    assert response.status_code == 409


def test_sms_otp_disable(client, make_user, auth_headers):
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    headers = auth_headers(authority)
    with patch("app.services.auth_service.send_sms") as mock_sms:
        client.post("/api/v1/auth/2fa/sms-otp/setup", json={"phone_number": "+15551234567"}, headers=headers)
        code = mock_sms.call_args.kwargs["body"].split(": ")[1].split(".")[0]
    client.post("/api/v1/auth/2fa/sms-otp/verify", json={"code": code}, headers=headers)

    response = client.post("/api/v1/auth/2fa/sms-otp/disable", headers=headers)
    assert response.status_code == 200
    assert response.json()["sms_otp_enabled"] is False


# ------------------------------------------------------- duplicate detection


def test_check_duplicates_finds_similar_nearby_case(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    headers = auth_headers(reporter)
    client.post("/api/v1/cases", json=CASE_PAYLOAD, headers=headers)

    response = client.post(
        "/api/v1/cases/check-duplicates",
        json={
            "name": "Jane Doe",
            "last_seen_location": {"lat": 15.85, "lng": 74.50},
            "last_seen_at": "2026-07-03T10:00:00Z",
        },
        headers=headers,
    )
    assert response.status_code == 200
    matches = response.json()
    assert len(matches) == 1
    assert matches[0]["name"] == "Jane Doe"
    assert matches[0]["similarity"] > 0.9


def test_check_duplicates_ignores_far_away_case(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    headers = auth_headers(reporter)
    client.post("/api/v1/cases", json=CASE_PAYLOAD, headers=headers)  # Belagavi

    response = client.post(
        "/api/v1/cases/check-duplicates",
        json={
            "name": "Jane Doe",
            "last_seen_location": {"lat": 19.0760, "lng": 72.8777},  # Mumbai, ~600km away
            "last_seen_at": "2026-07-01T10:00:00Z",
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == []


def test_check_duplicates_ignores_different_name(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    headers = auth_headers(reporter)
    client.post("/api/v1/cases", json=CASE_PAYLOAD, headers=headers)

    response = client.post(
        "/api/v1/cases/check-duplicates",
        json={
            "name": "Completely Different Person",
            "last_seen_location": {"lat": 15.85, "lng": 74.50},
            "last_seen_at": "2026-07-01T10:00:00Z",
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == []


def test_check_duplicates_ignores_far_apart_dates(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    headers = auth_headers(reporter)
    client.post("/api/v1/cases", json=CASE_PAYLOAD, headers=headers)  # 2026-07-01

    response = client.post(
        "/api/v1/cases/check-duplicates",
        json={
            "name": "Jane Doe",
            "last_seen_location": {"lat": 15.85, "lng": 74.50},
            "last_seen_at": "2026-12-01T10:00:00Z",  # months later
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == []


def test_filing_never_blocked_by_duplicate_match(client, make_user, auth_headers):
    """The core safety property: even an exact name/location/date match must
    never prevent filing a new case."""
    reporter = make_user(role=UserRole.REPORTER)
    headers = auth_headers(reporter)
    client.post("/api/v1/cases", json=CASE_PAYLOAD, headers=headers)

    response = client.post("/api/v1/cases", json=CASE_PAYLOAD, headers=headers)
    assert response.status_code == 201
    assert response.json()["possible_duplicates"] != []


def test_created_case_stores_possible_duplicates_snapshot(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    headers = auth_headers(reporter)
    first = client.post("/api/v1/cases", json=CASE_PAYLOAD, headers=headers).json()

    second = client.post("/api/v1/cases", json=CASE_PAYLOAD, headers=headers).json()
    assert len(second["possible_duplicates"]) == 1
    assert second["possible_duplicates"][0]["case_id"] == first["id"]

    # The first case, filed before the second existed, has no duplicates recorded.
    assert first["possible_duplicates"] == []


def test_dismissed_cases_excluded_from_duplicate_matches(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    first = client.post("/api/v1/cases", json=CASE_PAYLOAD, headers=auth_headers(reporter)).json()
    client.post(f"/api/v1/cases/{first['id']}/dismiss", headers=auth_headers(authority))

    response = client.post(
        "/api/v1/cases/check-duplicates",
        json={
            "name": "Jane Doe",
            "last_seen_location": {"lat": 15.85, "lng": 74.50},
            "last_seen_at": "2026-07-01T10:00:00Z",
        },
        headers=auth_headers(reporter),
    )
    assert response.json() == []
