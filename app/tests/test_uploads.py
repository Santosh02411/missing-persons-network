import io

from app.models.user import UserRole


def test_upload_requires_auth(client):
    response = client.post(
        "/api/v1/uploads/photo",
        files={"file": ("photo.jpg", io.BytesIO(b"fake-image-bytes"), "image/jpeg")},
    )
    assert response.status_code == 401


def test_upload_rejects_disallowed_content_type(client, make_user, auth_headers, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    user = make_user(role=UserRole.REPORTER)

    response = client.post(
        "/api/v1/uploads/photo",
        files={"file": ("notes.txt", io.BytesIO(b"just some text"), "text/plain")},
        headers=auth_headers(user),
    )
    assert response.status_code == 400


def test_upload_rejects_oversized_file(client, make_user, auth_headers, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 10)  # tiny limit for a fast test
    user = make_user(role=UserRole.REPORTER)

    oversized_content = b"x" * 1000
    response = client.post(
        "/api/v1/uploads/photo",
        files={"file": ("photo.jpg", io.BytesIO(oversized_content), "image/jpeg")},
        headers=auth_headers(user),
    )
    assert response.status_code == 413


def test_upload_succeeds_and_returns_media_url(client, make_user, auth_headers, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    user = make_user(role=UserRole.REPORTER)

    response = client.post(
        "/api/v1/uploads/photo",
        files={"file": ("photo.jpg", io.BytesIO(b"fake-image-bytes"), "image/jpeg")},
        headers=auth_headers(user),
    )
    assert response.status_code == 200
    body = response.json()
    assert "/media/" in body["url"]
    assert body["url"].endswith(".jpg")

    # File actually landed on disk under the (monkeypatched) upload dir.
    saved_files = list(tmp_path.iterdir())
    assert len(saved_files) == 1
