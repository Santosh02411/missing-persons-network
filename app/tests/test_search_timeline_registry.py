from app.models.user import UserRole

CASE_PAYLOAD = {
    "name": "Jane Doe",
    "description": "Last seen near the central market wearing a distinctive blue jacket with a torn sleeve.",
    "last_seen_location": {"lat": 15.8497, "lng": 74.4977},
    "last_seen_address": "Central Market, Belagavi",
    "last_seen_at": "2026-07-01T10:00:00Z",
}

OTHER_CASE_PAYLOAD = {
    "name": "Ravi Kumar",
    "description": "Last seen wearing a red cap near the railway station.",
    "last_seen_location": {"lat": 15.86, "lng": 74.51},
    "last_seen_address": "Railway Station, Belagavi",
    "last_seen_at": "2026-07-05T10:00:00Z",
}


def _create_and_approve(client, reporter_headers, authority_headers, payload=CASE_PAYLOAD) -> dict:
    response = client.post("/api/v1/cases", json=payload, headers=reporter_headers)
    assert response.status_code == 201, response.text
    case = response.json()
    approve = client.post(f"/api/v1/cases/{case['id']}/approve", headers=authority_headers)
    assert approve.status_code == 200
    return approve.json()


# ------------------------------------------------------------ full-text search


def test_search_matches_description_text(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    jane = _create_and_approve(client, auth_headers(reporter), auth_headers(authority), CASE_PAYLOAD)
    ravi = _create_and_approve(client, auth_headers(reporter), auth_headers(authority), OTHER_CASE_PAYLOAD)

    response = client.get("/api/v1/cases", params={"q": "torn sleeve"}, headers=auth_headers(reporter))
    assert response.status_code == 200
    ids = [c["id"] for c in response.json()]
    assert jane["id"] in ids
    assert ravi["id"] not in ids


def test_search_matches_word_stem(client, make_user, auth_headers):
    """Full-text search should match "jackets" against "jacket" (word
    stemming) -- something a plain ILIKE substring match wouldn't."""
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    jane = _create_and_approve(client, auth_headers(reporter), auth_headers(authority), CASE_PAYLOAD)

    response = client.get("/api/v1/cases", params={"q": "jackets"}, headers=auth_headers(reporter))
    assert response.status_code == 200
    assert jane["id"] in [c["id"] for c in response.json()]


def test_search_no_match_returns_empty(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    _create_and_approve(client, auth_headers(reporter), auth_headers(authority), CASE_PAYLOAD)

    response = client.get("/api/v1/cases", params={"q": "spaceship submarine"}, headers=auth_headers(reporter))
    assert response.status_code == 200
    assert response.json() == []


def test_search_combines_with_status_filter(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    jane = _create_and_approve(client, auth_headers(reporter), auth_headers(authority), CASE_PAYLOAD)
    client.patch(f"/api/v1/cases/{jane['id']}/status", json={"status": "resolved"}, headers=auth_headers(authority))

    response = client.get(
        "/api/v1/cases", params={"q": "jacket", "status": "open"}, headers=auth_headers(reporter)
    )
    assert jane["id"] not in [c["id"] for c in response.json()]

    response2 = client.get(
        "/api/v1/cases", params={"q": "jacket", "status": "resolved"}, headers=auth_headers(reporter)
    )
    assert jane["id"] in [c["id"] for c in response2.json()]


# ------------------------------------------------------------------- timeline


def test_timeline_includes_filing_and_approval(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    response = client.get(f"/api/v1/cases/{case['id']}/timeline", headers=auth_headers(reporter))
    assert response.status_code == 200
    events = response.json()
    types = [e["type"] for e in events]
    assert "case_filed" in types
    assert "case.approved" in types
    # chronological order
    timestamps = [e["timestamp"] for e in events]
    assert timestamps == sorted(timestamps)


def test_timeline_includes_status_changes_and_sightings(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    tipster = make_user(role=UserRole.REPORTER)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    client.patch(f"/api/v1/cases/{case['id']}/status", json={"status": "lead_found"}, headers=auth_headers(authority))
    client.post(
        "/api/v1/sightings",
        json={
            "case_id": case["id"],
            "location": {"lat": 15.86, "lng": 74.51},
            "address_text": "Bus stand, Belagavi",
            "description": "Saw someone matching",
        },
        headers=auth_headers(tipster),
    )

    response = client.get(f"/api/v1/cases/{case['id']}/timeline", headers=auth_headers(reporter))
    types = [e["type"] for e in response.json()]
    assert "case.status_changed" in types
    assert "sighting_reported" in types


def test_timeline_hides_internal_events_from_public_viewer(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    ngo = make_user(role=UserRole.AUTHORITY, is_verified=True)
    outsider = make_user(role=UserRole.REPORTER)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))
    client.post(
        f"/api/v1/cases/{case['id']}/collaborators",
        json={"authority_id": str(ngo.id)},
        headers=auth_headers(authority),
    )

    outsider_view = client.get(f"/api/v1/cases/{case['id']}/timeline", headers=auth_headers(outsider))
    outsider_types = [e["type"] for e in outsider_view.json()]
    assert "case.collaborator_added" not in outsider_types

    authority_view = client.get(f"/api/v1/cases/{case['id']}/timeline", headers=auth_headers(authority))
    authority_types = [e["type"] for e in authority_view.json()]
    assert "case.collaborator_added" in authority_types

    reporter_view = client.get(f"/api/v1/cases/{case['id']}/timeline", headers=auth_headers(reporter))
    reporter_types = [e["type"] for e in reporter_view.json()]
    assert "case.collaborator_added" in reporter_types  # the reporter sees full detail on their own case


# --------------------------------------------------------- NCMEC export stub


def test_ncmec_export_requires_case_access(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    unrelated_authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    response = client.get(f"/api/v1/cases/{case['id']}/export/ncmec", headers=auth_headers(unrelated_authority))
    assert response.status_code == 403

    response2 = client.get(f"/api/v1/cases/{case['id']}/export/ncmec", headers=auth_headers(authority))
    assert response2.status_code == 200
    assert response2.headers["content-type"] == "application/xml"
    assert b"<MissingPersonCase" in response2.content
    assert case["name"].encode() in response2.content


def test_ncmec_export_requires_authority_role(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    response = client.get(f"/api/v1/cases/{case['id']}/export/ncmec", headers=auth_headers(reporter))
    assert response.status_code == 403


def test_ncmec_sync_stub_makes_no_external_call_and_logs_audit(client, make_user, auth_headers, db_session):
    from app.models.audit_log import AuditLog

    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    response = client.post(f"/api/v1/cases/{case['id']}/export/ncmec/sync", headers=auth_headers(authority))
    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == case["id"]
    assert "no external call" in body["note"].lower() or "no data left" in body["note"].lower()

    from sqlalchemy import select

    log = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "case.registry_sync_stub")
    ).first()
    assert log is not None
    assert str(log.target_id) == case["id"]
