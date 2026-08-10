import io
from unittest.mock import patch

from app.models.user import UserRole

CASE_PAYLOAD = {
    "name": "Jane Doe",
    "description": "Last seen near the central market wearing a blue jacket.",
    "last_seen_location": {"lat": 15.8497, "lng": 74.4977},
    "last_seen_address": "Central Market, Belagavi",
    "last_seen_at": "2026-07-01T10:00:00Z",
}

VALID_CSV = (
    "name,description,last_seen_address,last_seen_lat,last_seen_lng,last_seen_at,age_at_disappearance,gender\n"
    "Amit Kumar,Last seen at the bus stand,MG Road Belagavi,15.85,74.50,2026-06-01,19,male\n"
    "Sita Devi,Went missing after school,Camp Road Belagavi,15.86,74.51,2026-06-15,12,female\n"
)


def _upload_csv(client, headers, content: str):
    return client.post(
        "/api/v1/cases/bulk-import",
        files={"file": ("cases.csv", io.BytesIO(content.encode()), "text/csv")},
        headers=headers,
    )


# --------------------------------------------------------------- bulk import


def test_bulk_import_requires_authority_or_admin(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    response = _upload_csv(client, auth_headers(reporter), VALID_CSV)
    assert response.status_code == 403


def test_bulk_import_creates_open_cases_owned_by_importer(client, make_user, auth_headers):
    ngo = make_user(role=UserRole.AUTHORITY, is_verified=True, org_name="Missing Children NGO")
    response = _upload_csv(client, auth_headers(ngo), VALID_CSV)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created_count"] == 2
    assert body["failed_count"] == 0
    assert len(body["created_case_ids"]) == 2

    case_id = body["created_case_ids"][0]
    detail = client.get(f"/api/v1/cases/{case_id}", headers=auth_headers(ngo))
    assert detail.status_code == 200
    case = detail.json()
    assert case["status"] == "open"
    assert case["assigned_authority_id"] == str(ngo.id)


def test_bulk_import_reports_row_errors_without_failing_whole_file(client, make_user, auth_headers):
    ngo = make_user(role=UserRole.AUTHORITY, is_verified=True)
    csv_content = (
        "name,description,last_seen_address,last_seen_lat,last_seen_lng,last_seen_at\n"
        "Good Row,Description here,Some address,15.85,74.50,2026-06-01\n"
        ",Missing name,Some address,15.85,74.50,2026-06-01\n"  # missing name
        "Bad Coords,Description,Some address,not-a-number,74.50,2026-06-01\n"  # bad lat
        "Bad Date,Description,Some address,15.85,74.50,not-a-date\n"  # bad date
    )
    response = _upload_csv(client, auth_headers(ngo), csv_content)
    assert response.status_code == 200
    body = response.json()
    assert body["created_count"] == 1
    assert body["failed_count"] == 3
    rows_with_errors = {e["row"] for e in body["errors"]}
    assert rows_with_errors == {3, 4, 5}


def test_bulk_import_rejects_missing_required_columns(client, make_user, auth_headers):
    ngo = make_user(role=UserRole.AUTHORITY, is_verified=True)
    bad_csv = "name,description\nSomeone,Description only\n"
    response = _upload_csv(client, auth_headers(ngo), bad_csv)
    assert response.status_code == 400
    assert "last_seen_address" in response.json()["detail"]


def test_bulk_imported_case_is_publicly_visible(client, make_user, auth_headers):
    ngo = make_user(role=UserRole.AUTHORITY, is_verified=True)
    other_user = make_user(role=UserRole.REPORTER)
    response = _upload_csv(client, auth_headers(ngo), VALID_CSV)
    case_id = response.json()["created_case_ids"][0]

    listing = client.get("/api/v1/cases", params={"status": "open"}, headers=auth_headers(other_user))
    assert case_id in [c["id"] for c in listing.json()]


# --------------------------------------------------------- sighting notify


def _create_and_approve(client, reporter_headers, authority_headers) -> dict:
    response = client.post("/api/v1/cases", json=CASE_PAYLOAD, headers=reporter_headers)
    assert response.status_code == 201
    case = response.json()
    approve = client.post(f"/api/v1/cases/{case['id']}/approve", headers=authority_headers)
    assert approve.status_code == 200
    return approve.json()


def test_assigned_authority_notified_immediately_on_new_sighting(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    tipster = make_user(role=UserRole.REPORTER)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))

    with patch("app.services.sighting_service.send_email") as mock_send:
        response = client.post(
            "/api/v1/sightings",
            json={
                "case_id": case["id"],
                "location": {"lat": 15.86, "lng": 74.51},
                "address_text": "Bus stand, Belagavi",
                "description": "Saw someone matching the description",
            },
            headers=auth_headers(tipster),
        )
        assert response.status_code == 201
        assert mock_send.call_count == 1
        assert mock_send.call_args.kwargs["to"] == authority.email
        assert "New sighting reported" in mock_send.call_args.kwargs["subject"]


def test_collaborator_also_notified_of_new_sighting(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    authority = make_user(role=UserRole.AUTHORITY, is_verified=True)
    ngo = make_user(role=UserRole.AUTHORITY, is_verified=True)
    tipster = make_user(role=UserRole.REPORTER)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(authority))
    client.post(
        f"/api/v1/cases/{case['id']}/collaborators",
        json={"authority_id": str(ngo.id)},
        headers=auth_headers(authority),
    )

    with patch("app.services.sighting_service.send_email") as mock_send:
        client.post(
            "/api/v1/sightings",
            json={
                "case_id": case["id"],
                "location": {"lat": 15.86, "lng": 74.51},
                "address_text": "Bus stand, Belagavi",
                "description": "Saw someone matching the description",
            },
            headers=auth_headers(tipster),
        )
        recipients = {c.kwargs["to"] for c in mock_send.call_args_list}
        assert recipients == {authority.email, ngo.email}


def test_no_notification_crash_when_case_unassigned(client, make_user, auth_headers, db_session):
    """A sighting on a case with no assigned authority (shouldn't normally
    happen for an OPEN case, but must degrade safely, not 500) sends no
    notification and still succeeds."""
    from app.models.case import Case, CaseStatus

    reporter = make_user(role=UserRole.REPORTER)
    tipster = make_user(role=UserRole.REPORTER)
    case = _create_and_approve(client, auth_headers(reporter), auth_headers(make_user(role=UserRole.AUTHORITY, is_verified=True)))

    db_obj = db_session.get(Case, case["id"])
    db_obj.assigned_authority_id = None
    db_session.commit()

    with patch("app.services.sighting_service.send_email") as mock_send:
        response = client.post(
            "/api/v1/sightings",
            json={
                "case_id": case["id"],
                "location": {"lat": 15.86, "lng": 74.51},
                "address_text": "Bus stand, Belagavi",
                "description": "Saw someone",
            },
            headers=auth_headers(tipster),
        )
        assert response.status_code == 201
        mock_send.assert_not_called()
