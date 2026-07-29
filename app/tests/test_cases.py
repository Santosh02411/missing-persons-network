from app.models.user import UserRole

CASE_PAYLOAD = {
    "name": "Jane Doe",
    "age_at_disappearance": 24,
    "description": "Last seen near the central market wearing a blue jacket.",
    "last_seen_location": {"lat": 15.8497, "lng": 74.4977},  # Belagavi
    "last_seen_address": "Central Market, Belagavi",
    "last_seen_at": "2026-07-01T10:00:00Z",
}


def _create_case(client, headers, **overrides) -> dict:
    payload = {**CASE_PAYLOAD, **overrides}
    response = client.post("/api/v1/cases", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_case_requires_auth(client):
    response = client.post("/api/v1/cases", json=CASE_PAYLOAD)
    assert response.status_code == 401


def test_create_and_read_case(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    case = _create_case(client, auth_headers(reporter))
    assert case["status"] == "open"
    assert case["last_seen_location"] == {"lat": 15.8497, "lng": 74.4977}

    response = client.get(f"/api/v1/cases/{case['id']}")
    assert response.status_code == 200
    assert response.json()["name"] == "Jane Doe"


def test_list_cases_is_public(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    _create_case(client, auth_headers(reporter))
    response = client.get("/api/v1/cases")
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_only_owner_can_edit_case(client, make_user, auth_headers):
    owner = make_user(role=UserRole.REPORTER)
    other_reporter = make_user(role=UserRole.REPORTER)
    case = _create_case(client, auth_headers(owner))

    response = client.patch(
        f"/api/v1/cases/{case['id']}",
        json={"name": "Changed Name"},
        headers=auth_headers(other_reporter),
    )
    assert response.status_code == 403

    response = client.patch(
        f"/api/v1/cases/{case['id']}",
        json={"name": "Changed Name"},
        headers=auth_headers(owner),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Changed Name"


def test_verified_authority_can_claim_unclaimed_case(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_case(client, auth_headers(reporter))

    response = client.post(f"/api/v1/cases/{case['id']}/claim", headers=auth_headers(authority))
    assert response.status_code == 200
    assert response.json()["assigned_authority_id"] == str(authority.id)


def test_unverified_authority_cannot_claim_case(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    unverified_authority = make_user(role=UserRole.AUTHORITY, is_verified=False)
    case = _create_case(client, auth_headers(reporter))

    response = client.post(
        f"/api/v1/cases/{case['id']}/claim", headers=auth_headers(unverified_authority)
    )
    assert response.status_code == 403


def test_claiming_an_already_claimed_case_conflicts(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority_a = make_user(role=UserRole.AUTHORITY, is_verified=True)
    authority_b = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_case(client, auth_headers(reporter))

    client.post(f"/api/v1/cases/{case['id']}/claim", headers=auth_headers(authority_a))
    response = client.post(f"/api/v1/cases/{case['id']}/claim", headers=auth_headers(authority_b))
    assert response.status_code == 409


def test_only_assigned_authority_can_change_status(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    assigned_authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    other_authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_case(client, auth_headers(reporter))
    client.post(f"/api/v1/cases/{case['id']}/claim", headers=auth_headers(assigned_authority))

    # A different (unassigned) verified authority still can't change status.
    response = client.patch(
        f"/api/v1/cases/{case['id']}/status",
        json={"status": "lead_found"},
        headers=auth_headers(other_authority),
    )
    assert response.status_code == 403

    response = client.patch(
        f"/api/v1/cases/{case['id']}/status",
        json={"status": "lead_found"},
        headers=auth_headers(assigned_authority),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "lead_found"


def test_reporter_cannot_change_case_status(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    case = _create_case(client, auth_headers(reporter))

    response = client.patch(
        f"/api/v1/cases/{case['id']}/status",
        json={"status": "resolved"},
        headers=auth_headers(reporter),
    )
    assert response.status_code == 403


def test_nearby_cases_returns_open_cases_within_radius(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    # Belagavi (near search point)
    _create_case(client, auth_headers(reporter), last_seen_location={"lat": 15.8497, "lng": 74.4977})
    # Mumbai (~500km away -- outside a small radius)
    _create_case(client, auth_headers(reporter), last_seen_location={"lat": 19.0760, "lng": 72.8777})

    response = client.get(
        "/api/v1/cases/nearby", params={"lat": 15.85, "lng": 74.50, "radius_km": 20}
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["name"] == "Jane Doe"
