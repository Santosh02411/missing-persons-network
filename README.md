# National Missing Persons & Reunification Network

Backend for a platform where families register missing person cases, the public
submits sighting reports, and verified authorities (police/NGOs) review and act on them.

## Status: Phase 1 of 5 — Architecture & DB Schema

This commit includes:
- Project skeleton (routers/services/models separation)
- SQLAlchemy models: `User`, `Case`, `Sighting`, `AuditLog`
- PostGIS `geography(Point, 4326)` columns for geo-search (Phase 4)
- Alembic migrations (hand-authored initial migration — see note below)
- Docker Compose: Postgres+PostGIS, Redis, API container
- `/health` endpoint with DB connectivity check

**Not yet implemented** (coming in later phases):
- Phase 2: API routes for auth/cases/sightings/admin
- Phase 3: JWT auth + RBAC enforcement
- Phase 4: Geo-search queries + Redis rate limiting
- Phase 5: pytest suite + GitHub Actions CI

## Local setup

```bash
cp .env.example .env
# edit .env — set a real SECRET_KEY

docker compose up --build
```

This starts Postgres (with PostGIS extension), Redis, and the API on `http://localhost:8000`.

Check it's alive:
```bash
curl http://localhost:8000/health
```

## Running migrations

```bash
docker compose exec api alembic upgrade head
```

> **Note on the initial migration:** it was hand-written to match `app/models/`
> rather than generated via `alembic revision --autogenerate`, since that requires
> a live DB connection. Once you run `docker compose up`, verify it with:
> ```bash
> docker compose exec api alembic check
> ```
> If it flags drift, regenerate: delete `alembic/versions/0001_initial_schema.py`,
> run `alembic revision --autogenerate -m "initial schema"`, and review the diff
> before applying.

## Project layout

```
app/
├── main.py              # FastAPI app, CORS, /health
├── core/config.py       # env-based settings
├── db/                  # engine, session, declarative base
├── models/              # SQLAlchemy ORM models
├── schemas/              # (Phase 2) Pydantic request/response models
├── api/v1/               # (Phase 2) route handlers
├── services/             # (Phase 2+) business logic
└── tests/                # (Phase 5) pytest suite
alembic/                  # migrations
```

## Design notes

- **Geo columns use PostGIS `geography(Point, 4326)`**, not separate lat/lng floats —
  enables `ST_DWithin` radius queries directly in SQL for Phase 4.
- **`reported_by` on Sighting is nullable** — supports anonymous public tips.
- **`AuditLog` is append-only** — tracks who changed case status / reviewed sightings,
  important for a domain involving vulnerable people's data.
- **Native Postgres enums** (`user_role`, `case_status`, `sighting_status`) enforce
  valid values at the DB level, not just in application code.
