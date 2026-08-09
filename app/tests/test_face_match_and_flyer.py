import io

from app.models.user import UserRole

CASE_PAYLOAD = {
    "name": "Jane Doe",
    "description": "Last seen near the central market wearing a blue jacket.",
    "last_seen_location": {"lat": 15.8497, "lng": 74.4977},
    "last_seen_address": "Central Market, Belagavi",
    "last_seen_at": "2026-07-01T10:00:00Z",
}


def _face_jpeg_bytes(variant: bool = False) -> bytes:
    """A real, detectable face photo (skimage's bundled sample), so face
    detection/matching has something genuine to work with -- optionally
    perturbed (brightness) to act as a "different photo, same person"."""
    import cv2
    import numpy as np
    from skimage import data

    img = cv2.cvtColor(data.astronaut(), cv2.COLOR_RGB2BGR)
    if variant:
        img = cv2.convertScaleAbs(img, alpha=1.0, beta=40)
    ok, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


def _upload_photo(client, headers, content: bytes) -> str:
    response = client.post(
        "/api/v1/uploads/photo",
        files={"file": ("photo.jpg", io.BytesIO(content), "image/jpeg")},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["url"]


def _create_case(client, headers, **overrides) -> dict:
    payload = {**CASE_PAYLOAD, **overrides}
    response = client.post("/api/v1/cases", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_sighting_gets_high_match_score_for_same_person(
    client, make_user, auth_headers, tmp_path, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    reporter = make_user(role=UserRole.REPORTER)
    headers = auth_headers(reporter)

    case_photo_url = _upload_photo(client, headers, _face_jpeg_bytes())
    case = _create_case(client, headers, photo_url=case_photo_url)

    sighting_photo_url = _upload_photo(client, headers, _face_jpeg_bytes(variant=True))
    response = client.post(
        "/api/v1/sightings",
        json={
            "case_id": case["id"],
            "location": {"lat": 15.86, "lng": 74.51},
            "address_text": "Bus stand, Belagavi",
            "description": "Saw someone matching the description",
            "photo_url": sighting_photo_url,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["photo_match_score"] is not None
    assert body["photo_match_score"] > 0.7


def test_sighting_match_score_is_none_without_a_photo(client, make_user, auth_headers, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    reporter = make_user(role=UserRole.REPORTER)
    headers = auth_headers(reporter)

    case_photo_url = _upload_photo(client, headers, _face_jpeg_bytes())
    case = _create_case(client, headers, photo_url=case_photo_url)

    response = client.post(
        "/api/v1/sightings",
        json={
            "case_id": case["id"],
            "location": {"lat": 15.86, "lng": 74.51},
            "address_text": "Bus stand, Belagavi",
            "description": "Saw someone matching the description",
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["photo_match_score"] is None


def test_sighting_match_score_is_none_when_no_face_detected(
    client, make_user, auth_headers, tmp_path, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    reporter = make_user(role=UserRole.REPORTER)
    headers = auth_headers(reporter)

    case_photo_url = _upload_photo(client, headers, _face_jpeg_bytes())
    case = _create_case(client, headers, photo_url=case_photo_url)

    # A tiny, blank JPEG has no face in it.
    import cv2
    import numpy as np

    blank = (np.ones((50, 50, 3), dtype="uint8") * 255)
    ok, buf = cv2.imencode(".jpg", blank)
    sighting_photo_url = _upload_photo(client, headers, buf.tobytes())

    response = client.post(
        "/api/v1/sightings",
        json={
            "case_id": case["id"],
            "location": {"lat": 15.86, "lng": 74.51},
            "address_text": "Bus stand, Belagavi",
            "description": "Saw someone matching the description",
            "photo_url": sighting_photo_url,
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["photo_match_score"] is None


def test_flyer_requires_auth(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    approver = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_case(client, auth_headers(reporter))
    client.post(f"/api/v1/cases/{case['id']}/approve", headers=auth_headers(approver))

    response = client.get(f"/api/v1/cases/{case['id']}/flyer")
    assert response.status_code == 401


def test_flyer_returns_a_pdf(client, make_user, auth_headers, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    reporter = make_user(role=UserRole.REPORTER)
    approver = make_user(role=UserRole.AUTHORITY, is_verified=True)
    headers = auth_headers(reporter)

    photo_url = _upload_photo(client, headers, _face_jpeg_bytes())
    case = _create_case(client, headers, photo_url=photo_url)
    client.post(f"/api/v1/cases/{case['id']}/approve", headers=auth_headers(approver))

    response = client.get(f"/api/v1/cases/{case['id']}/flyer", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_flyer_without_photo_still_generates(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    approver = make_user(role=UserRole.AUTHORITY, is_verified=True)
    case = _create_case(client, auth_headers(reporter))
    client.post(f"/api/v1/cases/{case['id']}/approve", headers=auth_headers(approver))

    response = client.get(f"/api/v1/cases/{case['id']}/flyer", headers=auth_headers(reporter))
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


def test_flyer_respects_case_visibility(client, make_user, auth_headers):
    reporter = make_user(role=UserRole.REPORTER)
    other_reporter = make_user(role=UserRole.REPORTER)
    # Case stays pending_review -- not approved -- so only the reporter or
    # an authority/admin can see it (case_service.get_case_or_404).
    case = _create_case(client, auth_headers(reporter))

    response = client.get(f"/api/v1/cases/{case['id']}/flyer", headers=auth_headers(other_reporter))
    assert response.status_code == 404
