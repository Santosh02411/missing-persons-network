import os
import uuid

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _ensure_upload_dir() -> None:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


async def save_upload(file: UploadFile) -> str:
    """Validates content-type and size, saves the file under settings.UPLOAD_DIR
    with a random filename (never trusts the client-supplied filename), and
    returns the path to mount it at (e.g. "abc123.jpg") -- the route builds
    the full URL, since that depends on the request's host.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{file.content_type}'. "
            f"Allowed: {', '.join(ALLOWED_CONTENT_TYPES)}.",
        )

    _ensure_upload_dir()
    extension = ALLOWED_CONTENT_TYPES[file.content_type]
    filename = f"{uuid.uuid4().hex}{extension}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)

    total_bytes = 0
    chunk_size = 1024 * 1024  # 1MB at a time, so a huge file can't be read fully into memory
    with open(filepath, "wb") as out_file:
        while chunk := await file.read(chunk_size):
            total_bytes += len(chunk)
            if total_bytes > settings.MAX_UPLOAD_BYTES:
                out_file.close()
                os.remove(filepath)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds the {settings.MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit.",
                )
            out_file.write(chunk)

    return filename


def read_upload_bytes(photo_url: str | None) -> bytes | None:
    """Reads a previously-uploaded file straight off local disk from its
    photo_url (always "<base>/media/<filename>", see api/v1/uploads.py and
    the /media/ StaticFiles mount in main.py), rather than making an HTTP
    request back to our own server. Returns None (never raises) for a
    missing photo_url, an unrecognized URL shape, or any read failure --
    callers (case sharing, face-match scoring) treat "no photo available"
    as an expected, non-fatal case."""
    if not photo_url:
        return None
    marker = "/media/"
    idx = photo_url.rfind(marker)
    if idx == -1:
        return None
    filename = photo_url[idx + len(marker) :]
    if not filename or "/" in filename or ".." in filename:
        return None
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    try:
        with open(filepath, "rb") as f:
            return f.read()
    except OSError:
        return None
