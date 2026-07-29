# Technical Architecture

## System diagram

```
┌─────────────┐      ┌──────────────────┐      ┌──────────────────┐
│   React     │─────▶│   FastAPI App    │─────▶│  PostgreSQL      │
│  Frontend   │◀─────│  (Uvicorn/ASGI)  │◀─────│  + PostGIS       │
└─────────────┘      └──────────────────┘      └──────────────────┘
                             │    │
                       ┌─────┘    └──────┐
                       ▼                 ▼
                  ┌─────────┐      ┌───────────┐
                  │  Redis  │      │  S3/Blob  │
                  │ rate    │      │ storage   │
                  │ limit + │      │ (photos)  │
                  │ cache   │      └───────────┘
                  └─────────┘
```

## Stack

| Layer | Choice | Why |
|---|---|---|
| API framework | FastAPI | async support, Pydantic validation, auto OpenAPI docs |
| DB | PostgreSQL + PostGIS | relational integrity + native geo-query support (`ST_DWithin`) |
| ORM | SQLAlchemy 2.0 (typed) + GeoAlchemy2 | type-safe models, geography column support |
| Migrations | Alembic | version-controlled schema changes |
| Auth | JWT (access + refresh) | stateless, standard for SPA + API architecture |
| Rate limiting/cache | Redis | fast, purpose-built for both token-bucket limiting and caching |
| Frontend | React | component-based SPA, wide ecosystem |
| Testing | pytest + httpx | async-friendly test client for FastAPI |
| CI | GitHub Actions | free for public repos, native GitHub integration |

## Data flow: submitting a sighting

1. Public user (authenticated or anonymous) hits `POST /api/v1/sightings`.
2. Redis-backed rate limiter checks request count for this IP/user against the configured limit.
3. Request validated against Pydantic schema (location, description required).
4. `sighting_service.create_sighting()` persists the row with `status = pending`.
5. Response returns the created sighting; no PII about other reporters is exposed.
6. An authority later calls `PATCH /api/v1/sightings/{id}/review` to verify/dismiss —
   this writes an `AuditLog` row and optionally updates the parent case's status.

## Database schema

See [PROJECT_REQUIREMENTS.md](./PROJECT_REQUIREMENTS.md) for functional context.
Full column-level detail lives in `app/models/*.py`; summary:

- **users** — account + role (`reporter` / `authority` / `admin`), `is_verified` gate for authorities.
- **cases** — the missing person record; `last_seen_location` is a PostGIS `geography(Point, 4326)`.
- **sightings** — tips against a case; `location` is also geography; `reported_by` nullable for anonymous tips.
- **audit_logs** — append-only record of sensitive actions (status changes, review decisions).

## Geo-query approach (implemented, Phase 4)

`services/geo_service.py`'s `nearby_sightings()`/`nearby_cases()` build the
query via SQLAlchemy (not raw SQL strings), casting the search point to
`Geography` so PostGIS computes distance in meters and can use the GiST index:

```python
point = cast(func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326), Geography)
select(Sighting)
    .where(func.ST_DWithin(Sighting.location, point, radius_m))
    .order_by(func.ST_Distance(Sighting.location, point))
```

This is the SQLAlchemy-expression equivalent of:

```sql
SELECT * FROM sightings
WHERE ST_DWithin(location, ST_MakePoint(:lng, :lat)::geography, :radius_meters)
ORDER BY location <-> ST_MakePoint(:lng, :lat)::geography;
```

Both use the GiST spatial index added in `alembic/versions/0002_geo_indexes.py`
instead of a full table scan. `nearby_cases()` additionally filters to
`CaseStatus.OPEN` — a resolved case showing up in a nearby-search result
isn't useful to someone searching.

## Rate limiting approach (implemented, Phase 4)

`core/rate_limit.py`'s `sighting_rate_limiter` uses a Redis fixed-window
counter (`INCR` + `EXPIRE`), keyed by user ID when authenticated or client IP
otherwise, wired into `POST /api/v1/sightings` as a route dependency. See
`docs/SECURITY_AND_ACCESS.md` for the tradeoffs of fixed-window vs.
token-bucket.
