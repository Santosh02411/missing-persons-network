# Feature Ticket List

Backlog organized by phase. Check items off as they're built; move details to
FEATURE_LOG.md when done.

## Phase 2 — API Endpoint Design

- [x] TICKET-201: Pydantic schemas for `User` (create/read/update), `Case`, `Sighting`
- [x] TICKET-202: `POST /api/v1/auth/register` — reporter/authority registration
- [x] TICKET-203: `POST /api/v1/auth/login` — returns access + refresh tokens
- [x] TICKET-204: `POST /api/v1/cases` — create case (auth required)
- [x] TICKET-205: `GET /api/v1/cases` — list/filter open cases (public)
- [x] TICKET-206: `GET /api/v1/cases/{id}` — case detail (public)
- [x] TICKET-207: `PATCH /api/v1/cases/{id}` — edit case (owner, assigned authority, or admin)
- [x] TICKET-207b: `POST /api/v1/cases/{id}/claim` (added in Phase 3) — authority claims a case (FR-3)
- [x] TICKET-208: `PATCH /api/v1/cases/{id}/status` — status transition (assigned authority or admin only)
- [x] TICKET-209: `POST /api/v1/sightings` — submit sighting (public, anon allowed)
- [x] TICKET-210: `PATCH /api/v1/sightings/{id}/review` — verify/dismiss (verified authority or admin only)
- [x] TICKET-211: `GET /api/v1/admin/authority-requests` — pending authority approvals
- [x] TICKET-212: `POST /api/v1/admin/authority-requests/{id}/approve`
- [x] TICKET-213: `case_service.py` — business logic layer for case CRUD + status transitions
- [x] TICKET-214: `sighting_service.py` — business logic layer for sighting CRUD + review

## Phase 3 — Auth/RBAC

- [x] TICKET-301: `core/security.py` — JWT encode/decode, password hash/verify
- [x] TICKET-302: `core/deps.py` — `get_current_user`, `require_role(*roles)` dependency
- [x] TICKET-303: Wire `require_role` into status-change and review endpoints
- [x] TICKET-304: Refresh token endpoint + rotation (plus `POST /api/v1/auth/logout`, added beyond original scope since rotation needed a revoke path anyway)
- [x] TICKET-305: Row-level ownership checks (reporter can only edit own case)
- [x] TICKET-306: Audit log writes on status change / sighting review

## Phase 4 — Geo-search & Rate Limiting

- [x] TICKET-401: `geo_service.py` — `ST_DWithin` query for nearby sightings
- [x] TICKET-402: `ST_DWithin` query for nearby open cases
- [x] TICKET-403: GiST spatial index migration on `location`/`last_seen_location`
- [x] TICKET-404 (custom Redis limiter, not slowapi): Redis rate limiter (`slowapi` or custom) on `POST /sightings`
- [x] TICKET-405: Redis caching for `GET /cases` list (short TTL, invalidate on write)
- [x] TICKET-406: `GET /api/v1/sightings/nearby?lat=&lng=&radius_km=` endpoint
- [x] TICKET-407: `GET /api/v1/cases/nearby?lat=&lng=&radius_km=` endpoint

## Phase 5 — Testing & CI/CD

- [x] TICKET-501: pytest fixtures — test DB (via testcontainers or a dedicated test Postgres), test client
- [x] TICKET-502: Unit tests for `case_service.py`, `sighting_service.py`
- [x] TICKET-503: Integration tests for auth flow (register/login/refresh)
- [x] TICKET-504: Integration tests for RBAC enforcement (403s where expected)
- [x] TICKET-505: Integration tests for geo-search endpoints
- [x] TICKET-506: GitHub Actions workflow — lint (ruff), test (pytest), on push/PR
- [x] TICKET-507: Coverage reporting in CI

## Frontend (parallel track, starts alongside Phase 2)

- [x] TICKET-601: React app scaffold (Vite), routing
- [x] TICKET-602: Auth pages (login/register) + token storage
- [x] TICKET-603: Case list + case detail pages
- [x] TICKET-604: Case creation form
- [x] TICKET-605: Sighting submission form with map picker
- [x] TICKET-606: Authority review dashboard
- [x] TICKET-607: Admin dashboard (authority approvals, audit log viewer)

## Post-launch feature batch (added after the original 5 phases + frontend)

- [x] TICKET-701: Audit log viewer — `GET /api/v1/admin/audit-logs` (admin only, filterable by target_type) + admin dashboard table
- [x] TICKET-702: Nearby-search UI — "Cases near me" button on the case list using browser geolocation + `/cases/nearby`
- [x] TICKET-703: Real photo upload — `POST /api/v1/uploads/photo` (content-type + size validated, served via `/media/`), `PhotoUpload` component wired into case creation and sighting submission
- [x] TICKET-704: Email verification — `email_verified` column (migration 0003), verification token flow (`/auth/verify-email`, `/auth/resend-verification`), stub email sender (`core/email.py`, logs instead of sending), frontend banner + `/verify-email` page
- [x] TICKET-705: Login lockout — Redis-backed failure counter, locks out for `LOGIN_LOCKOUT_SECONDS` after `LOGIN_FAILURE_THRESHOLD` consecutive failures per email, 429 + Retry-After
- [x] TICKET-706: Password reset — `/auth/forgot-password` (generic response, no account enumeration) + `/auth/reset-password` (revokes existing session), frontend pages
