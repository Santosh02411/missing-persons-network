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
- [x] TICKET-207: `PATCH /api/v1/cases/{id}` — edit case (owner or assigned authority)
- [x] TICKET-208 (endpoint built; role gate deferred to Phase 3): `PATCH /api/v1/cases/{id}/status` — status transition (authority only, Phase 3 gate)
- [x] TICKET-209: `POST /api/v1/sightings` — submit sighting (public, anon allowed)
- [x] TICKET-210 (endpoint built; role gate deferred to Phase 3): `PATCH /api/v1/sightings/{id}/review` — verify/dismiss (authority only, Phase 3 gate)
- [x] TICKET-211: `GET /api/v1/admin/authority-requests` — pending authority approvals
- [x] TICKET-212: `POST /api/v1/admin/authority-requests/{id}/approve`
- [x] TICKET-213: `case_service.py` — business logic layer for case CRUD + status transitions
- [x] TICKET-214: `sighting_service.py` — business logic layer for sighting CRUD + review

## Phase 3 — Auth/RBAC

- [ ] TICKET-301: `core/security.py` — JWT encode/decode, password hash/verify
- [ ] TICKET-302: `core/deps.py` — `get_current_user`, `require_role(*roles)` dependency
- [ ] TICKET-303: Wire `require_role` into status-change and review endpoints
- [ ] TICKET-304: Refresh token endpoint + rotation
- [ ] TICKET-305: Row-level ownership checks (reporter can only edit own case)
- [ ] TICKET-306: Audit log writes on status change / sighting review

## Phase 4 — Geo-search & Rate Limiting

- [ ] TICKET-401: `geo_service.py` — `ST_DWithin` query for nearby sightings
- [ ] TICKET-402: `ST_DWithin` query for nearby open cases
- [ ] TICKET-403: GiST spatial index migration on `location`/`last_seen_location`
- [ ] TICKET-404: Redis rate limiter (`slowapi` or custom) on `POST /sightings`
- [ ] TICKET-405: Redis caching for `GET /cases` list (short TTL, invalidate on write)
- [ ] TICKET-406: `GET /api/v1/sightings/nearby?lat=&lng=&radius_km=` endpoint
- [ ] TICKET-407: `GET /api/v1/cases/nearby?lat=&lng=&radius_km=` endpoint

## Phase 5 — Testing & CI/CD

- [ ] TICKET-501: pytest fixtures — test DB (via testcontainers or a dedicated test Postgres), test client
- [ ] TICKET-502: Unit tests for `case_service.py`, `sighting_service.py`
- [ ] TICKET-503: Integration tests for auth flow (register/login/refresh)
- [ ] TICKET-504: Integration tests for RBAC enforcement (403s where expected)
- [ ] TICKET-505: Integration tests for geo-search endpoints
- [ ] TICKET-506: GitHub Actions workflow — lint (ruff), test (pytest), on push/PR
- [ ] TICKET-507: Coverage reporting in CI

## Frontend (parallel track, starts alongside Phase 2)

- [ ] TICKET-601: React app scaffold (Vite), routing
- [ ] TICKET-602: Auth pages (login/register) + token storage
- [ ] TICKET-603: Case list + case detail pages
- [ ] TICKET-604: Case creation form
- [ ] TICKET-605: Sighting submission form with map picker
- [ ] TICKET-606: Authority review dashboard
- [ ] TICKET-607: Admin dashboard (authority approvals, audit log viewer)
