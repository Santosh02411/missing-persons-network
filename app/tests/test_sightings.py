from app.models.user import UserRole

CASE_PAYLOAD = {
    "name": "Jane Doe",
    "description": "Last seen near the central market.",
    "last_seen_location": {"lat": 15.8497, "lng": 74.4977},
    "last_seen_address": "Central Market, Belagavi",
    "last_seen_at": "2026-07-01T10:00:00Z",
}


def _create_case(client, headers) -> dict:
    response = client.post("/api/v1/cases", json=CASE_PAYLOAD, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _sighting_payload(case_id: str, **overrides) -> dict:
    payload = {
        "case_id": case_id,
        "location": {"lat": 15.86, "lng": 74.51},
        "address_text": "Bus stand, Belagavi",
        "description": "Saw someone matching the description",
    }
    payload.update(overrides)
    return payload


def test_anonymous_sighting_submission_allowed(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    case = _create_case(client, auth_headers(reporter))

    response = client.post("/api/v1/sightings", json=_sighting_payload(case["id"]))
    assert response.status_code == 201
    body = response.json()
    assert body["reported_by"] is None
    assert body["status"] == "pending"


def test_authenticated_sighting_submission_attributes_reporter(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    tipster = make_user(role=UserRole.REPORTER)
    case = _create_case(client, auth_headers(reporter))

    response = client.post(
        "/api/v1/sightings", json=_sighting_payload(case["id"]), headers=auth_headers(tipster)
    )
    assert response.status_code == 201
    assert response.json()["reported_by"] == str(tipster.id)


def test_sighting_submission_for_nonexistent_case_404s(client):
    response = client.post(
        "/api/v1/sightings", json=_sighting_payload("00000000-0000-0000-0000-000000000000")
    )
    assert response.status_code == 404


def test_sighting_rate_limit_returns_429_after_threshold(client, make_user, auth_headers, monkeypatch):
    from app.core.config import settings

    # Tighten the limit for this test so we don't need 5+ requests to trigger it.
    monkeypatch.setattr(settings, "SIGHTING_REPORT_RATE_LIMIT", "2/minute")

    reporter = make_user(role=UserRole.REPORTER)
    case = _create_case(client, auth_headers(reporter))

    first = client.post("/api/v1/sightings", json=_sighting_payload(case["id"]))
    second = client.post("/api/v1/sightings", json=_sighting_payload(case["id"]))
    third = client.post("/api/v1/sightings", json=_sighting_payload(case["id"]))

    assert first.status_code == 201
    assert second.status_code == 201
    assert third.status_code == 429
    assert "Retry-After" in third.headers


def test_only_verified_authority_can_review_sighting(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    unverified_authority = make_user(role=UserRole.AUTHORITY, is_verified=False)
    verified_authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_case(client, auth_headers(reporter))
    sighting = client.post(
        "/api/v1/sightings", json=_sighting_payload(case["id"])
    ).json()

    response = client.patch(
        f"/api/v1/sightings/{sighting['id']}/review",
        json={"status": "verified"},
        headers=auth_headers(unverified_authority),
    )
    assert response.status_code == 403

    response = client.patch(
        f"/api/v1/sightings/{sighting['id']}/review",
        json={"status": "verified"},
        headers=auth_headers(verified_authority),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "verified"
    assert body["reviewed_by"] == str(verified_authority.id)


def test_review_cannot_set_status_back_to_pending(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_case(client, auth_headers(reporter))
    sighting = client.post("/api/v1/sightings", json=_sighting_payload(case["id"])).json()

    response = client.patch(
        f"/api/v1/sightings/{sighting['id']}/review",
        json={"status": "pending"},
        headers=auth_headers(authority),
    )
    assert response.status_code == 400


def test_nearby_sightings_within_radius(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    case = _create_case(client, auth_headers(reporter))
    # Near the case
    client.post(
        "/api/v1/sightings",
        json=_sighting_payload(case["id"], location={"lat": 15.86, "lng": 74.51}),
    )
    # Far away (Mumbai)
    client.post(
        "/api/v1/sightings",
        json=_sighting_payload(case["id"], location={"lat": 19.0760, "lng": 72.8777}),
    )

    response = client.get(
        "/api/v1/sightings/nearby", params={"lat": 15.85, "lng": 74.50, "radius_km": 20}
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
