# Project Structure

```
missing-persons-network/
├── app/
│   ├── main.py              # FastAPI app factory, CORS, /health, router mounting
│   ├── core/
│   │   ├── config.py        # pydantic Settings — all env vars in one place
│   │   ├── security.py      # (Phase 3) JWT encode/decode, password hashing
│   │   └── deps.py          # (Phase 3) get_db, get_current_user, require_role()
│   ├── models/               # SQLAlchemy ORM models (one file per entity)
│   │   ├── user.py
│   │   ├── case.py
│   │   ├── sighting.py
│   │   └── audit_log.py
│   ├── schemas/              # (Phase 2) Pydantic request/response models
│   ├── api/v1/                # (Phase 2) route handlers — thin, delegate to services/
│   │   ├── auth.py
│   │   ├── cases.py
│   │   ├── sightings.py
│   │   └── admin.py
│   ├── services/              # (Phase 2+) business logic, kept out of routers
│   │   ├── case_service.py
│   │   ├── sighting_service.py
│   │   └── geo_service.py
│   ├── db/
│   │   ├── base_class.py     # shared declarative base (id, created_at, updated_at)
│   │   ├── base.py            # imports all models for Alembic autogenerate
│   │   └── session.py         # engine + get_db() dependency
│   └── tests/                 # (Phase 5) pytest suite
├── alembic/
│   ├── env.py                 # wired to app settings + models
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py
├── docs/                      # you are here
├── frontend/                  # (Phase 2+) React app
├── docker-compose.yml          # Postgres+PostGIS, Redis, API
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## Why this layout

- **Routers stay thin.** `app/api/v1/*.py` only handles request validation and
  delegates to `app/services/*.py`. This keeps business logic testable in
  isolation (call the service function directly in a unit test, no HTTP layer needed).
- **Models vs. Schemas separation.** SQLAlchemy models (`app/models/`) describe
  the DB. Pydantic schemas (`app/schemas/`) describe the API contract. Keeping
  them separate means an internal DB column can be added/renamed without
  automatically changing what the API exposes.
- **`db/base.py` exists solely for Alembic.** Nothing in application code should
  import from it — it's a one-purpose file to make autogenerate see all models.
- **`core/config.py` centralizes env access.** No module should call
  `os.environ` directly; everything reads from `settings`.
