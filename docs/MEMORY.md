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
3. **Auth/RBAC implementation** ✅ done
4. **Geo-search + Redis rate limiting** ✅ done
5. **Testing (pytest) + CI/CD (GitHub Actions)** ✅ done

All 5 backend phases complete. Remaining: frontend (parallel track).

Frontend (React) is a parallel track starting alongside Phase 2.

## What exists right now (Phase 1 through 5 -- backend complete)

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
  hashing + JWT access/refresh tokens, refresh tokens carry a `jti`);
  `core/deps.py` (`get_current_user`, `get_current_user_optional`,
  `require_role(*roles)`, `require_verified_authority_or_admin`);
  `core/redis_client.py`; `services/geo_service.py` (GeoPoint ↔ PostGIS
  conversion); `services/{auth,case,sighting,admin}_service.py`.
- Live routes: `/api/v1/auth/{register,login,refresh,logout}`,
  `/api/v1/cases` (CRUD + claim + status), `/api/v1/sightings` (submit, list, review),
  `/api/v1/admin/authority-requests` (list, approve).
- **RBAC is now enforced.** Status-change, sighting review, and admin
  endpoints require `require_verified_authority_or_admin` or
  `require_role(ADMIN)`. Case status change and case edit also have
  row-level checks (must be the assigned authority / owner / admin, not just
  the right role). Refresh tokens rotate on every `/refresh` call — reusing a
  stale one revokes the whole session (stored in Redis, keyed by user id).

- `services/geo_service.py`: `nearby_sightings()`/`nearby_cases()` using
  `ST_DWithin`/`ST_Distance` (cases restricted to OPEN status); GiST indexes
  added in `alembic/versions/0002_geo_indexes.py` (the Phase 1 hand-written
  migration didn't include these).
- Live routes added: `GET /api/v1/sightings/nearby`, `GET /api/v1/cases/nearby`.
- `core/rate_limit.py`: Redis fixed-window rate limiter on
  `POST /api/v1/sightings` (default 5/minute, keyed by user or IP).
- `core/cache.py`: versioned Redis cache on `GET /api/v1/cases`, invalidated
  by `case_service` on every write.
- Removed unused `slowapi` dependency (custom Redis limiter used instead).

- `app/tests/`: full pytest suite against a real second Postgres+PostGIS
  database (`TEST_DATABASE_URL`) and real Redis, using the standard
  SQLAlchemy "external transaction + SAVEPOINT" pattern for per-test
  isolation (see `conftest.py`). Covers auth (register/login/refresh
  rotation/logout), case CRUD + ownership + claim + status RBAC, sighting
  submission + rate limiting + review RBAC, admin RBAC, and service-layer
  unit tests.
- `.github/workflows/ci.yml`: lint (ruff) + test (pytest w/ coverage,
  `--cov-fail-under=70`) on every push/PR, using Postgres+PostGIS and Redis
  as GitHub Actions service containers.
- **Not actually run yet** — built and syntax-checked in a sandbox with no
  network access to install deps or run Postgres/Redis. Run
  `docker compose exec api pytest` locally to confirm before trusting it.

**Not built yet:** frontend (parallel track, was always meant to start
alongside Phase 2 — hasn't been picked up yet).

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
