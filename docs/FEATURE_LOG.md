# Feature Log

Chronological record of what's actually been built (not planned — see
FEATURE_TICKET_LIST.md for that). Newest entries at top.

---

### 2026-07-29 — Post-launch feature batch: audit logs, nearby search, uploads, email verification, lockout, password reset
**Status:** Done

- **Audit log viewer** (TICKET-701): `admin_service.list_audit_logs()` +
  `GET /api/v1/admin/audit-logs` (admin only, optional `target_type` filter),
  `AuditLogRead` schema. Frontend: a data table on `AdminDashboard` (new
  `.data-table` CSS). The `AuditLog` table had been recording since Phase 1
  with no way to read it back until now.
- **Nearby-search UI** (TICKET-702): "📍 Cases near me" button on `CaseList`
  using `navigator.geolocation`, calling the existing `/cases/nearby`
  endpoint. Toggles between normal filtered browsing and a
  location-radius view.
- **Real photo upload** (TICKET-703): `services/upload_service.py` validates
  content-type (`image/jpeg`/`png`/`webp` only) and streams the file in 1MB
  chunks to enforce `MAX_UPLOAD_BYTES` (default 5MB) without loading huge
  files into memory. `POST /api/v1/uploads/photo` (auth required — so
  anonymous sighting tips can't attach a photo unless the tipster logs in
  first), served back via a `StaticFiles` mount at `/media/`. Frontend:
  `PhotoUpload` component wired into `CaseCreate` and (auth-gated)
  `SightingForm`, replacing the old plain-URL text field.
- **Email verification** (TICKET-704): new `email_verified` column
  (`alembic/versions/0003_email_verified.py`), deliberately separate from
  `is_verified` (which gates authority permissions and is unrelated). Token
  flow via Redis (`email_verify:{token}` → user id, 24h TTL):
  `POST /auth/verify-email`, `POST /auth/resend-verification`. New
  `core/email.py` — a stub sender that logs instead of actually sending,
  since this project has no SMTP/email provider configured; every email
  call site (`auth_service.send_verification_email`,
  `auth_service.request_password_reset`) goes through this one function, so
  it's the only place to swap in a real provider later. **Deliberately
  doesn't block login or any action** on `email_verified` — with no real
  email delivery in this dev setup, locking users out entirely would just
  break the app; frontend shows a dismissable-by-verifying banner instead.
- **Login lockout** (TICKET-705): Redis fixed-window failure counter keyed
  by *email* (not user id — needed to rate-limit attempts against
  nonexistent emails too, without a different code path leaking which
  emails exist). After `LOGIN_FAILURE_THRESHOLD` (default 5) failures within
  `LOGIN_FAILURE_WINDOW_SECONDS` (default 15 min), locks for
  `LOGIN_LOCKOUT_SECONDS` (default 15 min), returning 429 + Retry-After. A
  successful login clears both counters.
- **Password reset** (TICKET-706): `POST /auth/forgot-password` always
  returns the same generic 202 response whether or not the email is
  registered (prevents account enumeration) — the reset email is only
  actually "sent" (logged) internally if the account exists.
  `POST /auth/reset-password` consumes a one-time Redis token (1h TTL) and,
  notably, **revokes the user's existing refresh session** on reset — if
  someone else had the account, a stolen session doesn't survive a
  password change. Frontend: `ForgotPassword.jsx`, `ResetPassword.jsx`.
- Tests added: `test_account_security.py` (email verification, password
  reset, login lockout — 13 tests), `test_uploads.py` (4 tests, using
  `monkeypatch` + `tmp_path` so nothing writes into the real `uploads/`
  dir), `test_audit_logs.py` (3 tests)
- Also fixed while touching `auth.py`: a leftover duplicate
  `from app.core.deps import get_current_user` import line from earlier
  editing

**Not run in this environment:** same caveat as every phase before this —
no network access here to actually run `pytest`, `npm install`, or a
browser. Syntax-checked and manually traced through; verify locally.

---

### 2026-07-27 — Frontend: authority + admin dashboards (TICKET-606/607)
**Status:** Done

- **Backend additions** (no dashboard-worthy endpoints existed for these):
  - `GET /api/v1/cases/assigned-to-me` — cases assigned to the calling
    authority (`case_service.list_assigned_cases`), verified-authority/admin
    only, registered before `/{case_id}`
  - `GET /api/v1/sightings/pending` — global pending-review queue
    (`sighting_service.list_pending_sightings`, eager-loads the parent case
    via `joinedload` so each row can include `case_name` without an N+1
    query), verified-authority/admin only. New `SightingQueueItem` schema
    (`SightingRead` + `case_name`).
  - Tests added: `test_assigned_to_me_returns_only_this_authoritys_cases`,
    `test_assigned_to_me_requires_verified_authority`,
    `test_pending_queue_includes_case_name_and_requires_verified_authority`,
    `test_pending_queue_excludes_already_reviewed_sightings`
- **Frontend**: `AuthorityDashboard` (pending queue with inline
  Verify/Dismiss, assigned-cases list; shows a plain "awaiting approval"
  message instead of erroring for unverified authority accounts) and
  `AdminDashboard` (pending authority approvals with an Approve button),
  both role-gated via `ProtectedRoute`'s `allowedRoles`, linked from the
  masthead nav that was already wired up

**Not built yet:** audit-log viewer (mentioned in the original ticket title
but not built — no backend endpoint exists yet to list audit logs; would
need one), any UI for nearby-search.

---

### 2026-07-27 — Frontend, first pass (+ a backend security fix)
**Status:** Core flows done; authority/admin dashboards not yet built

- Vite + React scaffold: `frontend/` — routing (`react-router-dom`), axios
  API client with automatic access-token refresh on 401 (de-duplicated across
  concurrent failures), `AuthContext` for session state
- Pages: `Login`, `Register` (reporter or authority signup), `CaseList`
  (status filter chips), `CaseDetail` (info, map, sightings list, sighting
  form, inline claim/status controls for authorities), `CaseCreate`
  (map-based last-seen location picker), `NotFound`
- Components: `Masthead` (role-aware nav), `CaseCard`, `StatusBadge`,
  `SightingForm`, `LocationPicker` (Leaflet + OpenStreetMap tiles),
  `ProtectedRoute`
- Design: calm civic-registry palette (cool ink/slate/cloud — deliberately
  not the cream+terracotta or near-black+neon AI-default looks), Lora
  (display) + Inter (body) + IBM Plex Mono (data/labels); signature element
  is a diagonal "status ribbon" in each case card's corner, color-keyed to
  case status
- **Backend fix, found while building the register form**: `UserCreate.role`
  previously accepted the full `UserRole` enum, including `admin` — with no
  verification gate on admin the way authority has `is_verified`, this was a
  straight privilege-escalation hole (anyone could POST `role: "admin"` and
  get full admin access). Fixed: `role` is now
  `Literal["reporter", "authority"]` in `app/schemas/user.py`; admin accounts
  are not self-registerable through this endpoint at all. Regression test
  added: `test_register_cannot_self_grant_admin_role` in `app/tests/test_auth.py`.
- **Backend addition**: `GET /api/v1/auth/me` — didn't exist before; added
  because the frontend needs a way to identify the logged-in user (and their
  role) from a stored token after a page reload.

**Not built yet:** authority review-queue dashboard (TICKET-606), admin
dashboard for authority approvals (TICKET-607 — the backend endpoint exists,
no UI yet), any UI for the `/cases/nearby` / `/sightings/nearby` endpoints.

**Not run in this environment:** no network access to `npm install`, so
nothing here has actually been built or run in a browser. Files were
syntax-reviewed (brace/paren balance, default-export presence) but not
executed — run `npm install && npm run dev` locally and report back if
anything breaks.

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
