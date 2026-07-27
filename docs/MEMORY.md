# Project Memory

> Paste this file into a new AI chat (or re-read it yourself) to resume work on
> this project without re-explaining everything from scratch.

## What this is

**National Missing Persons & Reunification Network** — an SDE portfolio
project. Families register missing person cases; the public submits
rate-limited sighting reports; verified authorities (police/NGOs) review
sightings and update case status (`Open → Lead Found → Resolved`); geo-search
finds nearby sightings/cases.

## Stack

FastAPI (Python) · PostgreSQL + PostGIS · SQLAlchemy 2.0 + GeoAlchemy2 ·
Alembic · JWT auth with RBAC (reporter / authority / admin) · Redis (rate
limiting + caching) · React frontend · pytest + GitHub Actions CI · Docker
Compose for local dev.

## Build approach

Being built in 5 sequential phases, each producing real runnable code (not
just design docs):

1. **Architecture & DB schema** ✅ done
2. **API endpoint design** (routes, request/response models) ✅ done
3. **Auth/RBAC implementation** ⏳ next
4. **Geo-search + Redis rate limiting**
5. **Testing (pytest) + CI/CD (GitHub Actions)**

Frontend (React) is a parallel track starting alongside Phase 2.

## What exists right now (Phase 1 + 2)

- `app/models/`: `User`, `Case`, `Sighting`, `AuditLog` — full SQLAlchemy
  models with a shared base (`db/base_class.py`) giving UUID PK + timestamps.
- PostGIS `geography(Point, 4326)` columns on `Case.last_seen_location` and
  `Sighting.location`, ready for `ST_DWithin` geo-queries in Phase 4.
- Alembic fully wired, one hand-written initial migration creating all
  tables/enums + enabling the PostGIS extension.
- `docker-compose.yml` (Postgres+PostGIS, Redis, API), `Dockerfile`,
  `.env.example`, `requirements.txt`.
- `/health` endpoint with DB connectivity check.
- Full `docs/` folder (this file lives there).

- Pydantic schemas for user/token/geo/case/sighting; `core/security.py` (bcrypt
  hashing + JWT access/refresh tokens); `core/deps.py` (`get_current_user`,
  `get_current_user_optional`); `services/geo_service.py` (GeoPoint ↔ PostGIS
  conversion); `services/{auth,case,sighting,admin}_service.py`.
- Live routes: `/api/v1/auth/{register,login,refresh}`,
  `/api/v1/cases` (CRUD + status), `/api/v1/sightings` (submit, list, review),
  `/api/v1/admin/authority-requests` (list, approve).
- **Important:** none of these routes enforce role-based access yet. Any
  authenticated user can currently call status-change, review, or admin
  endpoints — every such route has a `TODO(phase-3)` docstring marking it.

**Not built yet:** RBAC role enforcement (`require_role()`), row-level
ownership checks beyond basic case-edit, geo-search queries, rate limiting,
tests, CI pipeline, frontend.

## Key design decisions already made (don't re-litigate these)

- Geo columns are PostGIS `geography`, not plain lat/lng floats — enables
  server-side radius queries via `ST_DWithin` instead of app-level Haversine.
- `Sighting.reported_by` is nullable — anonymous public tips are a real
  requirement for this domain.
- `AuditLog` is a separate append-only table, not scattered soft-delete flags
  — tracks who changed what (case status, sighting review decisions).
- Authority accounts require admin approval (`is_verified`) before they can
  review sightings or change case status — prevents self-declared authority.
- Routers stay thin; business logic lives in `app/services/`.

## Where to look for more detail

- `docs/PROJECT_REQUIREMENTS.md` — full functional/non-functional requirements
- `docs/TECHNICAL_ARCHITECTURE.md` — system diagram, data flow, schema rationale
- `docs/SECURITY_AND_ACCESS.md` — RBAC matrix, JWT details, rate limiting design
- `docs/DESIGN_AND_FRONTEND_SPECS.md` — planned React pages/components
- `docs/FEATURE_TICKET_LIST.md` — the actual backlog, ticket by ticket
- `docs/FEATURE_LOG.md` — chronological record of what shipped when

## How the user likes to work

Wants real, working code delivered as files/zips — not just explanations or
suggestions. Prefers a phased, one-thing-at-a-time build order rather than
everything at once.
