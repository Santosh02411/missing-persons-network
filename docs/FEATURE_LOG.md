# Feature Log

Chronological record of what's actually been built (not planned — see
FEATURE_TICKET_LIST.md for that). Newest entries at top.

---

### 2026-07-27 — Phase 5: Testing & CI/CD
**Status:** Done

- `app/tests/conftest.py`: test fixtures backed by a **real** second
  Postgres+PostGIS database (`TEST_DATABASE_URL`, separate from dev data) and
  real Redis — no DB/cache mocking, so geo-search and rate-limiting logic
  runs against the same engine as production.
  - `db_session` fixture uses the standard SQLAlchemy "join a Session into
    an external transaction" pattern (outer transaction + SAVEPOINT,
    auto-restarted on each `commit()`) so tests can call service functions
    that commit freely, and every test still rolls back cleanly afterward.
  - `client` fixture overrides `get_db` so the FastAPI `TestClient` uses the
    transactional test session.
  - `_clean_redis` (autouse) flushes rate-limit/refresh-token/cache keys
    before and after every test — Redis state isn't part of the DB
    transaction rollback, so it needs separate cleanup.
  - `make_user` factory fixture, `auth_headers` helper for building
    `Authorization` headers from a user.
- Integration tests: `test_auth.py` (register/login/refresh rotation +
  reuse-detection/logout), `test_cases.py` (CRUD, ownership, claim, status
  gating, nearby geo-search), `test_sightings.py` (anonymous + attributed
  submission, rate-limit 429, review gating, nearby geo-search),
  `test_admin.py` (RBAC on authority approval endpoints)
- Unit tests: `services/test_case_service.py`, `services/test_sighting_service.py`
  — call the service layer directly, no HTTP round-trip
- `scripts/init-test-db.sql`: creates the separate test database + enables
  PostGIS on first `docker compose up` (mounted into the `db` service)
- `pytest.ini`, `pyproject.toml` (ruff config), `requirements-dev.txt` (adds
  `ruff` on top of `requirements.txt`)
- `.github/workflows/ci.yml`: on every push/PR — spins up Postgres+PostGIS
  and Redis as service containers, lints with `ruff`, creates the test DB
  (service containers don't support the `docker-entrypoint-initdb.d` mount
  trick used locally), runs the full suite with coverage
  (`--cov-fail-under=70`), uploads coverage XML as an artifact

**Not run in this environment:** the actual test suite hasn't been executed
here — this sandbox has no network access to install dependencies or spin up
Postgres/Redis. Every file was syntax-checked (`py_compile`) and manually
reviewed, but run it locally via `docker compose exec api pytest` to confirm
before relying on it.

---

### 2026-07-27 — Phase 4: Geo-search & Rate Limiting
**Status:** Done

- `services/geo_service.py`: `nearby_sightings()` (FR-10) and `nearby_cases()`
  (FR-11, restricted to `OPEN` cases) using `ST_DWithin` + `ST_Distance`
  ordering, with points cast to `Geography` so distances are in meters and
  the spatial index gets used
- `alembic/versions/0002_geo_indexes.py`: GiST indexes on
  `cases.last_seen_location` and `sightings.location` (the hand-written
  initial migration in Phase 1 didn't include these — GeoAlchemy2's
  auto-index DDL hooks only fire through declarative `Base.metadata`, not
  through the raw `op.create_table()` calls used there)
- `GET /api/v1/sightings/nearby?lat=&lng=&radius_km=&limit=`
- `GET /api/v1/cases/nearby?lat=&lng=&radius_km=&limit=` (registered before
  `/{case_id}` in the router so FastAPI doesn't try to parse "nearby" as a
  case UUID)
- `core/rate_limit.py`: `sighting_rate_limiter` — Redis fixed-window counter
  (`INCR`+`EXPIRE`), keyed by user id when authenticated or client IP
  otherwise, enforcing `SIGHTING_REPORT_RATE_LIMIT` (default `5/minute`).
  Returns `429` with a `Retry-After` header. Wired into
  `POST /api/v1/sightings` via a route-level dependency.
- `core/cache.py`: versioned cache for `GET /api/v1/cases` — cache key
  includes a version counter bumped by `case_service` on every write
  (create/update/claim/status-change), so the 30s TTL is a read-load
  backstop, not the primary invalidation path
- Removed the unused `slowapi` dependency — custom Redis limiter used
  instead (simpler to reason about for this scope, documented tradeoff:
  fixed-window over sliding/token-bucket)

---

### 2026-07-27 — Phase 3: Auth/RBAC Implementation
**Status:** Done

- `core/deps.py`: `require_role(*roles)` dependency factory (403s on wrong
  role); `require_verified_authority_or_admin` — stricter check that also
  blocks authority accounts pending admin approval (`is_verified=False`)
- `core/redis_client.py`: shared Redis client (also reused by Phase 4's rate
  limiting/caching)
- `core/security.py`: refresh tokens now carry a `jti`; added
  `decode_refresh_token()` returning `{user_id, jti}` for rotation checks
- `services/auth_service.py`: `store_refresh_jti`, `is_refresh_jti_valid`,
  `revoke_refresh_token` — Redis-backed, one valid refresh token per user at
  a time
- `api/v1/auth.py`: `/refresh` now rotates (issues a new access+refresh pair
  and invalidates the old one); reused/stale refresh tokens revoke the whole
  session rather than just failing; added `POST /api/v1/auth/logout`
- `services/case_service.py`: added `claim_case()` (FR-3 — an authority takes
  ownership of a case, rejects re-claiming an already-assigned case); row-level
  checks added to `update_case()` (owner, assigned authority, or admin) and
  `update_case_status()` (assigned authority or admin only, checked against
  *this specific case's* `assigned_authority_id`)
- Routes now gated:
  - `POST /api/v1/cases/{id}/claim` (new) and
    `PATCH /api/v1/cases/{id}/status` → `require_verified_authority_or_admin`
  - `PATCH /api/v1/sightings/{id}/review` → `require_verified_authority_or_admin`
  - `GET/POST /api/v1/admin/authority-requests*` → `require_role(ADMIN)`
- All `TODO(phase-3)` markers from Phase 2 removed and resolved

**Design note:** sighting review is gated by role only (any verified
authority can review any pending sighting) — no case-assignment scoping,
unlike case status changes which are scoped to the specific assigned
authority. See docs/SECURITY_AND_ACCESS.md for the full RBAC matrix.

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
