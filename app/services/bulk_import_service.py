"""Bulk CSV case import -- lets a verified authority/NGO migrate existing
case records into the registry in one upload instead of filing them one at
a time through the normal form.

Design choice worth flagging: cases created this way go straight to OPEN
with assigned_authority_id set to the importer, skipping the normal
pending_review -> approve step that reporter-filed cases go through. That's
deliberate, not an oversight -- the importer is already a verified
authority account (the same trust level as whoever would approve a
reporter's case), so requiring them to then approve their own bulk import
would just be a redundant extra step, not a real additional safety check.
"""
import csv
import io
from datetime import datetime

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.cache import bump_cases_list_version
from app.models.case import Case, CaseStatus
from app.models.user import User
from app.services.geo_service import to_geography
from app.services import watch_service
from app.schemas.geo import GeoPoint

REQUIRED_COLUMNS = {"name", "description", "last_seen_address", "last_seen_lat", "last_seen_lng", "last_seen_at"}
OPTIONAL_COLUMNS = {"age_at_disappearance", "gender", "photo_url"}
MAX_ROWS = 500


def _parse_row(row: dict, row_number: int) -> tuple[dict | None, list[str]]:
    errors = []

    name = (row.get("name") or "").strip()
    if not name:
        errors.append("name is required")

    description = (row.get("description") or "").strip()
    if not description:
        errors.append("description is required")

    address = (row.get("last_seen_address") or "").strip()
    if not address:
        errors.append("last_seen_address is required")

    lat = lng = None
    try:
        lat = float(row.get("last_seen_lat", ""))
        lng = float(row.get("last_seen_lng", ""))
        GeoPoint(lat=lat, lng=lng)  # reuses the same range validation as the API schema
    except (TypeError, ValueError) as exc:
        errors.append(f"last_seen_lat/last_seen_lng: {exc}")

    last_seen_at = None
    raw_date = (row.get("last_seen_at") or "").strip()
    try:
        last_seen_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
    except ValueError:
        errors.append("last_seen_at must be an ISO 8601 date/datetime, e.g. 2026-07-01 or 2026-07-01T10:00:00Z")

    age = None
    raw_age = (row.get("age_at_disappearance") or "").strip()
    if raw_age:
        try:
            age = int(raw_age)
            if not (0 <= age <= 130):
                errors.append("age_at_disappearance must be between 0 and 130")
                age = None
        except ValueError:
            errors.append("age_at_disappearance must be a whole number")

    if errors:
        return None, errors

    return {
        "name": name,
        "description": description,
        "last_seen_address": address,
        "last_seen_lat": lat,
        "last_seen_lng": lng,
        "last_seen_at": last_seen_at,
        "age_at_disappearance": age,
        "gender": (row.get("gender") or "").strip() or None,
        "photo_url": (row.get("photo_url") or "").strip() or None,
    }, []


def bulk_import_cases(db: Session, file_bytes: bytes, importer: User) -> dict:
    try:
        text = file_bytes.decode("utf-8-sig")  # -sig strips an Excel-exported BOM if present
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Couldn't read the file as UTF-8 text. Export the CSV with UTF-8 encoding and try again.",
        )

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The file has no header row.")

    missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing_columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required column(s): {', '.join(sorted(missing_columns))}",
        )

    rows = list(reader)
    if len(rows) > MAX_ROWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many rows ({len(rows)}). Split the file into batches of {MAX_ROWS} or fewer.",
        )

    row_errors = []
    created_cases = []
    for i, row in enumerate(rows, start=2):  # row 1 is the header
        parsed, errors = _parse_row(row, i)
        if errors:
            row_errors.append({"row": i, "errors": errors})
            continue

        case = Case(
            created_by=importer.id,
            name=parsed["name"],
            age_at_disappearance=parsed["age_at_disappearance"],
            gender=parsed["gender"],
            photo_url=parsed["photo_url"],
            description=parsed["description"],
            last_seen_location=to_geography(GeoPoint(lat=parsed["last_seen_lat"], lng=parsed["last_seen_lng"])),
            last_seen_address=parsed["last_seen_address"],
            last_seen_at=parsed["last_seen_at"],
            status=CaseStatus.OPEN,
            assigned_authority_id=importer.id,
            target_authority_id=importer.id,
        )
        db.add(case)
        created_cases.append(case)

    # One commit for the whole valid batch, rather than per-row, so a
    # partially-processed file can't leave the DB with some rows committed
    # and others not depending on where an error happened.
    db.commit()
    for case in created_cases:
        db.refresh(case)
        watch_service.watch_case(db, case, importer)  # importer auto-watches their own imported cases, same as filing one normally
    if created_cases:
        bump_cases_list_version()

    return {
        "created_count": len(created_cases),
        "failed_count": len(row_errors),
        "created_case_ids": [c.id for c in created_cases],
        "errors": row_errors,
    }


async def read_csv_upload(file: UploadFile) -> bytes:
    if file.content_type not in ("text/csv", "application/vnd.ms-excel", "application/octet-stream", None):
        # Not a hard rejection on content_type alone (browsers/OSes are
        # inconsistent about what they report for .csv) -- just a soft
        # signal; the real validation is whether it parses as CSV with the
        # right columns, done in bulk_import_cases.
        pass
    return await file.read()
