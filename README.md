# National Missing Persons & Reunification Network

Backend for a platform where families register missing person cases, the public
submits sighting reports, and verified authorities (police/NGOs) review and act on them.

## Status: Phase 2 of 5 done, Phase 3 in progress

This includes:
- Project skeleton (routers/services/models separation)
- SQLAlchemy models: `User`, `Case`, `Sighting`, `AuditLog`
- PostGIS `geography(Point, 4326)` columns for geo-search (Phase 4)
- Alembic migrations (hand-authored initial migration — see note below)
- Docker Compose: Postgres+PostGIS, Redis, API container
- `/health` endpoint with a real DB connectivity check (returns HTTP 503, not 200, if the DB is unreachable)
- Full API routes for auth, cases, sightings, admin (Phase 2)
- Role-based access control and refresh token rotation (Phase 3, in progress)

**Not yet implemented** (coming in later phases):
- Phase 4: Geo-search queries + Redis rate limiting
- Phase 5: pytest suite + GitHub Actions CI

## Local setup

```bash
cp .env.example .env
# edit .env — set a real SECRET_KEY (DATABASE_URL and REDIS_URL are already
# correct for running via Docker Compose — see "Understanding the
# connections" below before changing them)

docker compose up --build
```

This starts Postgres (with PostGIS extension), Redis, and the API on `http://localhost:8000`.

Check it's alive:
```bash
curl http://localhost:8000/health
```
A healthy response looks like `{"status": "ok", "database": "connected", ...}`
with HTTP 200. If you get HTTP 503 and `"database": "unreachable"`, see the
troubleshooting note at the end of the next section — it's almost always a
`DATABASE_URL`/`REDIS_URL` hostname problem.

## Understanding the connections (Docker networking, explained)

This trips people up constantly, so here's the short version and the long version.

### The short version

- Things run in **containers**: one for the API, one for Postgres, one for Redis.
- Containers talk to each other using their **service name** as the hostname
  (`db`, `redis`) — never `localhost`.
- Your browser/terminal on your actual Windows machine talks to containers
  using **`localhost` + the published port** (`localhost:8000`, `localhost:5432`).
- Two different "networks" are in play, and `localhost` means something
  different on each one. That's the whole source of confusion.

### The long version

`docker-compose.yml` defines three services:

```yaml
services:
  db:      # Postgres — reachable by other containers as "db"
  redis:   # Redis    — reachable by other containers as "redis"
  api:     # FastAPI  — reachable by other containers as "api"
```

Docker Compose automatically creates a private virtual network
(`missing-persons-network_default`, visible in your Docker Desktop screenshot)
and puts all three containers on it. **On that private network, each
container can reach the others by service name** — Docker's internal DNS
resolves `db` to the Postgres container's IP, `redis` to the Redis
container's IP, automatically. This is why `app/core/config.py`'s
`DATABASE_URL` should say `db`, not `localhost`: from the API container's
point of view, `db` *is* the address of the Postgres container.

`localhost` (or `127.0.0.1`) always means "this same machine/container I'm
currently running in." So:
- Inside the **api** container, `localhost` = the api container itself (no
  Postgres there → connection refused).
- Inside the **db** container, `localhost` = the db container itself.
- On **your Windows machine**, `localhost` = your Windows machine.

These are three different "machines" as far as networking is concerned, even
though Docker Desktop makes them all feel like they're on your one PC.

### Why `docker compose exec api alembic upgrade head` failed for you

That command runs `alembic upgrade head` **inside the running `api`
container** (that's what `exec` does — it executes a command inside an
already-running container, rather than starting a new one). Alembic reads
`DATABASE_URL` from your `.env`, which had `localhost` in it. From inside the
`api` container, `localhost` doesn't point at Postgres — it points at the
`api` container itself, which has nothing listening on port 5432. Hence
`Connection refused`. Changing it to `db` fixes it because that's the actual
address of the Postgres container on the shared Docker network.

### The other half: published ports

You'll notice `docker-compose.yml` also has this for each service:

```yaml
ports:
  - "5432:5432"   # db
  - "6379:6379"   # redis
  - "8000:8000"   # api
```

This is a **different** kind of connection: it "publishes" a port from
inside the container out to your host machine (your actual Windows PC).
`"8000:8000"` means "whatever is listening on port 8000 inside the container,
make it reachable at `localhost:8000` from my Windows machine too." That's
why:
- Your browser can hit `http://localhost:8000/docs` — that request comes
  from *outside* Docker, from Windows, so `localhost` correctly means "my PC,"
  and the port mapping forwards it into the `api` container.
- A GUI tool like pgAdmin or DBeaver running on Windows can connect to
  `localhost:5432` to poke at the database directly, using the port mapping —
  even though *inside* Docker, other containers use `db:5432` instead.

So there are genuinely two separate address books:
| From... | Reach Postgres via | Reach Redis via | Reach the API via |
|---|---|---|---|
| Another container (e.g. `api`) | `db:5432` | `redis:6379` | `api:8000` |
| Your Windows machine / browser | `localhost:5432` | `localhost:6379` | `localhost:8000` |

`.env`'s `DATABASE_URL`/`REDIS_URL` are read by code running *inside* the
`api` container, so they belong in the top row — hence `db` and `redis`, not
`localhost`.

### If you ever run the API directly on Windows (no Docker)

If you `pip install -r requirements.txt` and run `uvicorn app.main:app`
directly on your machine instead of via `docker compose up`, then *your
Windows machine* is now the one running the API code — so at that point
`localhost` in `.env` would be correct again (assuming Postgres/Redis are
also running directly on Windows, or you're using the port-mapped
`localhost:5432`/`localhost:6379` from a still-running `docker compose up`
for just `db`/`redis`). This project is designed to be run fully via Docker
Compose, so you generally shouldn't need to do this — but it's why the
`.env.example` comments call this out explicitly.

## Running migrations

```bash
docker compose exec api alembic upgrade head
```

> **Getting `Connection refused` on `localhost:5432`?** Your `.env`'s
> `DATABASE_URL` has the wrong hostname for running inside Docker — it needs
> to say `db`, not `localhost`. See "Understanding the connections" above for
> why, and `.env.example` for the corrected value.

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
├── main.py              # FastAPI app, CORS, /health, router mounting
├── core/                # config, security (JWT/hashing), deps (auth + role checks)
├── db/                  # engine, session, declarative base
├── models/              # SQLAlchemy ORM models
├── schemas/              # Pydantic request/response models
├── api/v1/               # route handlers (auth, cases, sightings, admin)
├── services/             # business logic
└── tests/                # (Phase 5) pytest suite
alembic/                  # migrations
docs/                     # full project documentation — start at docs/README.md
```

## Design notes

- **Geo columns use PostGIS `geography(Point, 4326)`**, not separate lat/lng floats —
  enables `ST_DWithin` radius queries directly in SQL for Phase 4.
- **`reported_by` on Sighting is nullable** — supports anonymous public tips.
- **`AuditLog` is append-only** — tracks who changed case status / reviewed sightings,
  important for a domain involving vulnerable people's data.
- **Native Postgres enums** (`user_role`, `case_status`, `sighting_status`) enforce
  valid values at the DB level, not just in application code.
