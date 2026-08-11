from app.models.user import UserRole

CASE_PAYLOAD = {
    "name": "Jane Doe",
    "description": "Last seen near the central market wearing a blue jacket.",
    "last_seen_location": {"lat": 15.8497, "lng": 74.4977},
    "last_seen_address": "Central Market, Belagavi",
    "last_seen_at": "2026-07-01T10:00:00Z",
}


def _create_and_approve(client, reporter_headers, authority_headers, payload=CASE_PAYLOAD) -> dict:
    response = client.post("/api/v1/cases", json=payload, headers=reporter_headers)
    assert response.status_code == 201, response.text
    case = response.json()
    approve = client.post(f"/api/v1/cases/{case['id']}/approve", headers=authority_headers)
    assert approve.status_code == 200
    return approve.json()


# ------------------------------------------------------------ age progression


def test_only_case_access_can_set_age_progression(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    unrelated_authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    response = client.patch(
        f"/api/v1/cases/{case['id']}/age-progression",
        json={"age_progressed_photo_url": "http://testserver/media/aged.jpg", "age_progression_note": "Est. age 15"},
        headers=auth_headers(unrelated_authority),
    )
    assert response.status_code == 403

    response2 = client.patch(
        f"/api/v1/cases/{case['id']}/age-progression",
        json={"age_progressed_photo_url": "http://testserver/media/aged.jpg", "age_progression_note": "Est. age 15"},
        headers=auth_headers(authority),
    )
    assert response2.status_code == 200
    body = response2.json()
    assert body["age_progressed_photo_url"] == "http://testserver/media/aged.jpg"
    assert body["age_progression_note"] == "Est. age 15"

    # Original photo untouched (still None here, since the case was filed without one)
    assert body["photo_url"] is None


def test_reporter_cannot_set_age_progression(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    response = client.patch(
        f"/api/v1/cases/{case['id']}/age-progression",
        json={"age_progressed_photo_url": "http://testserver/media/aged.jpg"},
        headers=auth_headers(reporter),
    )
    assert response.status_code == 403


def test_collaborator_can_set_age_progression(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    ngo = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))
    client.post(
        f"/api/v1/cases/{case['id']}/collaborators",
        json={"authority_id": str(ngo.id)},
        headers=auth_headers(authority),
    )

    response = client.patch(
        f"/api/v1/cases/{case['id']}/age-progression",
        json={"age_progressed_photo_url": "http://testserver/media/aged.jpg"},
        headers=auth_headers(ngo),
    )
    assert response.status_code == 200


# --------------------------------------------------------- physical identifiers


def test_case_stores_physical_identifiers(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    payload = {
        **CASE_PAYLOAD,
        "height_cm": 150,
        "eye_color": "brown",
        "hair_color": "black",
        "blood_type": "O+",
        "distinguishing_marks": "Small star tattoo on right ankle, scar above left eyebrow.",
        "medical_conditions": "Type 1 diabetic, needs insulin.",
    }
    response = client.post("/api/v1/cases", json=payload, headers=auth_headers(reporter))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["height_cm"] == 150
    assert body["blood_type"] == "O+"
    assert "star tattoo" in body["distinguishing_marks"]
    assert "diabetic" in body["medical_conditions"]


def test_invalid_blood_type_rejected(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    payload = {**CASE_PAYLOAD, "blood_type": "Z++"}
    response = client.post("/api/v1/cases", json=payload, headers=auth_headers(reporter))
    assert response.status_code == 422


def test_filter_cases_by_blood_type(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    o_positive = _create_and_approve(
        client, auth_headers(reporter), auth_headers(authority), {**CASE_PAYLOAD, "name": "OPos", "blood_type": "O+"}
    )
    a_negative = _create_and_approve(
        client, auth_headers(reporter), auth_headers(authority), {**CASE_PAYLOAD, "name": "ANeg", "blood_type": "A-"}
    )

    response = client.get("/api/v1/cases", params={"blood_type": "O+"}, headers=auth_headers(reporter))
    ids = [c["id"] for c in response.json()]
    assert o_positive["id"] in ids
    assert a_negative["id"] not in ids


def test_distinguishing_marks_are_full_text_searchable(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(
        client,
        auth_headers(reporter),
        auth_headers(authority),
        {**CASE_PAYLOAD, "distinguishing_marks": "Distinctive butterfly-shaped birthmark on the neck."},
    )

    response = client.get("/api/v1/cases", params={"q": "butterfly birthmark"}, headers=auth_headers(reporter))
    assert case["id"] in [c["id"] for c in response.json()]


def test_physical_identifiers_updatable_after_filing(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    response = client.post("/api/v1/cases", json=CASE_PAYLOAD, headers=auth_headers(reporter))
    case = response.json()
    assert case["blood_type"] is None

    update = client.patch(
        f"/api/v1/cases/{case['id']}", json={"blood_type": "AB+"}, headers=auth_headers(reporter)
    )
    assert update.status_code == 200
    assert update.json()["blood_type"] == "AB+"


# ------------------------------------------------------------- emergency contacts


def test_emergency_contacts_public_no_auth_required(client):
    response = client.get("/api/v1/emergency-contacts")
    assert response.status_code == 200
    contacts = response.json()
    assert len(contacts) > 0
    assert all({"label", "number", "description"} <= set(c.keys()) for c in contacts)
    numbers = [c["number"] for c in contacts]
    assert "112" in numbers
    assert "100" in numbers
