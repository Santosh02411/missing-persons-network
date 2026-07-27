# Feature Log

Chronological record of what's actually been built (not planned — see
FEATURE_TICKET_LIST.md for that). Newest entries at top.

---

### 2026-07-27 — Phase 2: API Endpoint Design
**Status:** Done

- Pydantic schemas: `UserCreate`/`UserRead`/`UserLogin` (`schemas/user.py`),
  `Token`/`TokenPayload`/`RefreshRequest` (`schemas/token.py`), `GeoPoint`
  (`schemas/geo.py`), `CaseCreate`/`CaseUpdate`/`CaseStatusUpdate`/`CaseRead`/
  `CaseListItem` (`schemas/case.py`), `SightingCreate`/`SightingReview`/
  `SightingRead` (`schemas/sighting.py`)
- `core/security.py`: bcrypt password hashing, JWT access/refresh token
  creation and decoding (needed to make login actually work — pulled forward
  from Phase 3's original scope)
- `core/deps.py`: `get_current_user` (required auth) and
  `get_current_user_optional` (for endpoints like sighting submission that
  allow anonymous access)
- `services/geo_service.py`: `to_geography()`/`from_geography()` converting
  between API-level `GeoPoint` and PostGIS geography columns
- `services/auth_service.py`: registration (authority accounts start
  unverified) and login
- `services/case_service.py`: create/read/list/update case, plus
  status-change with an `AuditLog` write
- `services/sighting_service.py`: create/read/list sightings, plus review
  (verify/dismiss) with an `AuditLog` write
- `services/admin_service.py`: list pending authority requests, approve
- Routes mounted in `main.py`:
  - `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`
  - `POST /api/v1/cases`, `GET /api/v1/cases`, `GET /api/v1/cases/{id}`,
    `PATCH /api/v1/cases/{id}`, `PATCH /api/v1/cases/{id}/status`
  - `POST /api/v1/sightings`, `GET /api/v1/sightings/case/{case_id}`,
    `PATCH /api/v1/sightings/{id}/review`
  - `GET /api/v1/admin/authority-requests`, `POST /api/v1/admin/authority-requests/{id}/approve`

**Known gap, by design:** none of these routes enforce role-based access yet
— any authenticated user can currently call status-change, review, or admin
endpoints. Every such route is marked `TODO(phase-3)` at its definition.
Role enforcement (`require_role()`) and row-level ownership checks land in
Phase 3.

---

### 2026-07-27 — Phase 1: Architecture & DB Schema
**Status:** Done

- Project skeleton: `app/{core,models,schemas,api/v1,services,db,tests}`
- SQLAlchemy models: `User` (with `UserRole` enum: reporter/authority/admin),
  `Case` (with `CaseStatus` enum: open/lead_found/resolved), `Sighting` (with
  `SightingStatus` enum: pending/verified/dismissed), `AuditLog`
- PostGIS `geography(Point, 4326)` columns on `Case.last_seen_location` and
  `Sighting.location` for future geo-search
- Shared declarative base (`app/db/base_class.py`) giving every model a UUID
  PK + `created_at`/`updated_at` for free
- Alembic wired up (`alembic/env.py` reads settings + all models); hand-written
  initial migration (`0001_initial_schema.py`) creating all tables, enums, and
  enabling the PostGIS extension
- `docker-compose.yml`: Postgres+PostGIS, Redis, API containers with healthchecks
- `Dockerfile`, `requirements.txt`, `.env.example`
- `/health` endpoint with live DB connectivity check
- `docs/` — full documentation set (this folder)

**Not yet implemented:** API routes, auth/RBAC enforcement, geo-search queries,
rate limiting, tests, CI.
