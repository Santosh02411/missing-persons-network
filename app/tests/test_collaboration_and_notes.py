from app.models.user import UserRole

CASE_PAYLOAD = {
    "name": "Jane Doe",
    "description": "Last seen near the central market wearing a blue jacket.",
    "last_seen_location": {"lat": 15.8497, "lng": 74.4977},
    "last_seen_address": "Central Market, Belagavi",
    "last_seen_at": "2026-07-01T10:00:00Z",
}


def _create_and_approve(client, reporter_headers, authority_headers) -> dict:
    response = client.post("/api/v1/cases", json=CASE_PAYLOAD, headers=reporter_headers)
    assert response.status_code == 201, response.text
    case = response.json()
    approve = client.post(f"/api/v1/cases/{case['id']}/approve", headers=authority_headers)
    assert approve.status_code == 200
    return approve.json()


# -------------------------------------------------------------- case notes


def test_reporter_cannot_see_or_add_notes(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    assert client.get(f"/api/v1/cases/{case['id']}/notes", headers=auth_headers(reporter)).status_code == 403
    assert client.post(
        f"/api/v1/cases/{case['id']}/notes", json={"body": "trying to add a note"}, headers=auth_headers(reporter)
    ).status_code == 403


def test_unrelated_authority_cannot_see_or_add_notes(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    other_authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    assert client.get(f"/api/v1/cases/{case['id']}/notes", headers=auth_headers(other_authority)).status_code == 403
    assert client.post(
        f"/api/v1/cases/{case['id']}/notes", json={"body": "sneaking a note in"}, headers=auth_headers(other_authority)
    ).status_code == 403


def test_assigned_authority_and_admin_can_add_and_read_notes(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    admin = make_user(role=UserRole.ADMIN, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    response = client.post(
        f"/api/v1/cases/{case['id']}/notes",
        json={"body": "Spoke to a witness near the market, following up tomorrow."},
        headers=auth_headers(authority),
    )
    assert response.status_code == 201
    note = response.json()
    assert note["author_name"]
    assert note["body"] == "Spoke to a witness near the market, following up tomorrow."

    admin_view = client.get(f"/api/v1/cases/{case['id']}/notes", headers=auth_headers(admin))
    assert admin_view.status_code == 200
    assert len(admin_view.json()) == 1


def test_notes_not_included_in_public_case_detail(client, make_user, auth_headers):
    """Notes must only ever be reachable via the dedicated notes endpoint,
    never leaked through the regular case detail response."""
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    client.post(
        f"/api/v1/cases/{case['id']}/notes",
        json={"body": "Sensitive internal detail."},
        headers=auth_headers(authority),
    )
    detail = client.get(f"/api/v1/cases/{case['id']}", headers=auth_headers(reporter))
    assert "Sensitive internal detail." not in detail.text
    assert "notes" not in detail.json()


# ------------------------------------------------------------ collaborators


def test_add_and_list_collaborator(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True, org_name="Belagavi Police")
    ngo = make_user(role=UserRole.AUTHORITY, is_verified=True, org_name="Missing Children NGO")
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    response = client.post(
        f"/api/v1/cases/{case['id']}/collaborators",
        json={"authority_id": str(ngo.id)},
        headers=auth_headers(authority),
    )
    assert response.status_code == 201
    assert response.json()["org_name"] == "Missing Children NGO"

    listing = client.get(f"/api/v1/cases/{case['id']}/collaborators", headers=auth_headers(authority))
    assert listing.status_code == 200
    assert [c["user_id"] for c in listing.json()] == [str(ngo.id)]


def test_only_assigned_authority_or_admin_can_add_collaborator(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    other_authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    ngo = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    response = client.post(
        f"/api/v1/cases/{case['id']}/collaborators",
        json={"authority_id": str(ngo.id)},
        headers=auth_headers(other_authority),
    )
    assert response.status_code == 403


def test_collaborator_gains_full_case_access(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    ngo = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    # Before being added, the NGO has none of this access.
    assert client.get(f"/api/v1/cases/{case['id']}/notes", headers=auth_headers(ngo)).status_code == 403
    assert client.patch(
        f"/api/v1/cases/{case['id']}/status", json={"status": "lead_found"}, headers=auth_headers(ngo)
    ).status_code == 403

    client.post(
        f"/api/v1/cases/{case['id']}/collaborators",
        json={"authority_id": str(ngo.id)},
        headers=auth_headers(authority),
    )

    # After being added, the NGO has the same access as the assigned authority.
    assert client.get(f"/api/v1/cases/{case['id']}/notes", headers=auth_headers(ngo)).status_code == 200
    note = client.post(
        f"/api/v1/cases/{case['id']}/notes", json={"body": "NGO following up on a lead."}, headers=auth_headers(ngo)
    )
    assert note.status_code == 201
    status_change = client.patch(
        f"/api/v1/cases/{case['id']}/status", json={"status": "lead_found"}, headers=auth_headers(ngo)
    )
    assert status_change.status_code == 200


def test_collaborator_can_remove_self(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    ngo = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))
    client.post(
        f"/api/v1/cases/{case['id']}/collaborators", json={"authority_id": str(ngo.id)}, headers=auth_headers(authority)
    )

    response = client.delete(f"/api/v1/cases/{case['id']}/collaborators/{ngo.id}", headers=auth_headers(ngo))
    assert response.status_code == 204
    assert client.get(f"/api/v1/cases/{case['id']}/notes", headers=auth_headers(ngo)).status_code == 403


def test_cannot_add_unverified_authority_as_collaborator(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    unverified = make_user(role=UserRole.AUTHORITY, is_verified=False)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    response = client.post(
        f"/api/v1/cases/{case['id']}/collaborators",
        json={"authority_id": str(unverified.id)},
        headers=auth_headers(authority),
    )
    assert response.status_code == 400


def test_adding_same_collaborator_twice_is_idempotent(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    ngo = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    r1 = client.post(
        f"/api/v1/cases/{case['id']}/collaborators", json={"authority_id": str(ngo.id)}, headers=auth_headers(authority)
    )
    r2 = client.post(
        f"/api/v1/cases/{case['id']}/collaborators", json={"authority_id": str(ngo.id)}, headers=auth_headers(authority)
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    listing = client.get(f"/api/v1/cases/{case['id']}/collaborators", headers=auth_headers(authority))
    assert len(listing.json()) == 1
