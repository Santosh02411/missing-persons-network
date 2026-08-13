# National Missing Persons & Reunification Network

A full-stack platform where families and the public register missing person
cases, report sightings, and verified police stations / NGOs review and act
on them. Cases are routed to a specific nearby (or explicitly chosen) station
rather than broadcast to every authority nationwide, and that station keeps
ownership of approving/dismissing the case, reviewing sightings on it,
updating its status, and sharing it with other authorities.

**Stack:** FastAPI + PostgreSQL/PostGIS + Redis on the backend, React (Vite)
on the frontend.

---

## Features

- **Case filing & routing** — a reporter files a case with a photo, last-seen
  location, and description. It's auto-routed to the nearest verified
  station within range (or the reporter's explicit choice), and stays
  private (`pending_review`) until that station approves it.
- **Case review & lifecycle** — approve / dismiss / claim / change status
  (open → lead found → resolved) / reopen a resolved case, all scoped to the
  case's assigned station (or an admin) — see `docs/SECURITY_AND_ACCESS.md`.
- **Sighting reports** — the public (or anonymous visitors) report sightings
  against a case; reviewed (verified/dismissed) by whichever station has
  access to that case, same scoping as case actions.
- **Multi-authority collaboration** — the assigned station can add other
  verified authorities as collaborators on a case, and share full case
  details (with photo) to another authority by email, with a link back into
  the app.
- **Two-factor authentication** — TOTP (authenticator app), email OTP, or SMS
  OTP (via Twilio); email/SMS backends default to `console` (just logged) so
  the project runs with zero external accounts out of the box.
- **Geofenced alerts** — an opt-in, community-scale analog of an Amber Alert:
  notifies subscribers near a case's last-seen location.
- **Duplicate detection** — flags likely-duplicate cases at filing time.
- **Face-similarity scoring** — best-effort match score between a sighting's
  photo and the case's photo (classical CV, not a deep model — see
  `app/services/face_match_service.py` for why).
- **Age-progressed photos** — authorities can attach an age-progressed image
  to long-open cases, shown alongside the original.
- **Printable flyers** — one-page PDF with photo, key details, and a QR code
  linking back to the case.
- **Bulk import** — CSV import of existing case records for authorities/NGOs
  migrating data.
- **NCMEC-style export** — generates a document-style XML export per case
  (a stub/simulation, not a live external integration).
- **Admin tools** — authority account verification, analytics dashboard,
  audit log.
- **Nearby search** — PostGIS-backed radius search for cases and sightings.
- **Emergency contacts** — shown on every case page, not gated behind login.

---

## Project structure

```
missing-persons-network/
├── app/                          # FastAPI backend
│   ├── main.py                   # App instance, CORS, /health, router mounting
│   ├── core/                     # config, security (JWT/hashing), deps (auth + role
│   │                              guards), rate limiting, redis client, cache,
│   │                              email + SMS sending backends
│   ├── db/                       # engine, session, declarative base
│   ├── models/                   # SQLAlchemy ORM models
│   │   ├── user.py                 User (role: reporter/authority/admin, 2FA fields)
│   │   ├── case.py                 Case (status, geo location, routing fields)
│   │   ├── case_collaborator.py    Multi-authority collaboration on a case
│   │   ├── case_note.py            Private investigation-log entries
│   │   ├── case_watch.py           Email-subscription ("watch") on a case
│   │   ├── sighting.py             Sighting reports against a case
│   │   └── audit_log.py            Append-only action log
│   ├── schemas/                  # Pydantic request/response models
│   ├── api/v1/                   # Route handlers
│   │   ├── auth.py                 Register/login/2FA/password reset/email verify
│   │   ├── cases.py                 CRUD + approve/dismiss/claim/status/share/reopen
│   │   ├── sightings.py             Submit + review + nearby
│   │   ├── admin.py                 Authority verification, audit log
│   │   ├── authorities.py           Authority directory/search (for sharing, collab)
│   │   ├── emergency.py             Emergency contact numbers (no auth required)
│   │   └── uploads.py               Photo upload handling
│   ├── services/                 # Business logic (one module per domain concern:
│   │                              case_service, sighting_service, auth_service,
│   │                              alert_service, duplicate_detection_service,
│   │                              face_match_service, flyer_service,
│   │                              bulk_import_service, collaboration_service,
│   │                              timeline_service, watch_service, geo_service,
│   │                              analytics_service, registry_export_service,
│   │                              admin_service, authority_service, upload_service)
│   └── tests/                    # pytest suite (route-level + service-level)
├── alembic/                      # DB migrations
├── scripts/
│   └── init-test-db.sql          # Auto-creates the test DB on first `docker compose up`
├── docs/                         # Deeper documentation — start at docs/README.md
│   ├── SECURITY_AND_ACCESS.md      RBAC matrix, row-level access rules
│   ├── TECHNICAL_ARCHITECTURE.md
│   ├── PROJECT_STRUCTURE.md
│   ├── PROJECT_REQUIREMENTS.md
│   ├── PROJECT_WORKFLOW.md
│   ├── DESIGN_AND_FRONTEND_SPECS.md
│   ├── FEATURE_LOG.md
│   └── FEATURE_TICKET_LIST.md
├── frontend/                     # React (Vite) frontend
│   ├── index.html
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx                 Routes
│       ├── main.jsx                 Entry point
│       ├── api/                     Axios client + per-domain API calls
│       ├── context/                 AuthContext (session/user state)
│       ├── styles/index.css         Design system (tokens, components, utilities)
│       ├── pages/                   One file per route (CaseList, CaseDetail,
│       │                            CaseCreate, Login, Register, Profile,
│       │                            AccountSecurity, CitizenDashboard,
│       │                            AuthorityDashboard, AdminDashboard,
│       │                            AdminAnalytics, SuccessStories, ForgotPassword,
│       │                            ResetPassword, VerifyEmail, NotFound)
│       └── components/              Masthead, AuthLayout, CaseCard, CaseInvestigation
│                                    Panel, SightingForm, ShareCaseForm, PhotoUpload,
│                                    LocationPicker, StationPicker, NearbyCasesMap,
│                                    PasswordField, StatusBadge, MatchScoreBadge,
│                                    BulkImportForm, EmergencyContactsBanner,
│                                    EmailVerificationBanner, ReunitedCard,
│                                    ProtectedRoute
├── docker-compose.yml             # Postgres+PostGIS, Redis, API containers
├── Dockerfile                     # API container build
├── requirements.txt                # Backend runtime dependencies
├── requirements-dev.txt            # + lint/dev tooling (ruff)
├── pytest.ini / pyproject.toml
├── alembic.ini
└── .env.example                   # Backend env var template (copy to .env)
```

---

## Local setup

You can run this either **via Docker Compose** (recommended — Postgres,
PostGIS, and Redis are all handled for you) or **natively** (Postgres/Redis
installed and running on your own machine). Docker is simpler if you have it;
native is what to use if you don't.

### Option A — Docker Compose

```bash
cp .env.example .env
# edit .env — set a real SECRET_KEY at minimum. DATABASE_URL/REDIS_URL are
# already correct for Docker (host "db"/"redis") — see the networking note
# below before changing them.

docker compose up --build
```

This starts Postgres (with PostGIS), Redis, and the API on
`http://localhost:8000`. Then run migrations:

```bash
docker compose exec api alembic upgrade head
```

Check it's alive:

```bash
curl http://localhost:8000/health
```

A healthy response is HTTP 200, `{"status": "ok", "database": "connected", ...}`.
HTTP 503 / `"database": "unreachable"` almost always means `DATABASE_URL` in
`.env` has the wrong hostname for this context — see the networking note below.

### Option B — Native (no Docker)

Requires Python 3.11+, PostgreSQL with the PostGIS extension, and Redis,
all installed and running locally.

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
# edit .env:
#   - SECRET_KEY: any long random string, e.g. `python -c "import secrets; print(secrets.token_hex(32))"`
#   - DATABASE_URL / TEST_DATABASE_URL: change host "db" -> "localhost"
#     e.g. postgresql+psycopg2://mpn_user:mpn_pass@localhost:5432/mpn_db
#   - REDIS_URL: change host "redis" -> "localhost"
#     e.g. redis://localhost:6379/0
# (create the mpn_user/mpn_db database + role yourself, and enable the
# postgis extension on it: CREATE EXTENSION IF NOT EXISTS postgis;)

alembic upgrade head
uvicorn app.main:app --reload
```

API is now on `http://localhost:8000`.

### Frontend (either option)

```bash
cd frontend
npm install
cp .env.example .env    # VITE_API_BASE_URL defaults to http://localhost:8000/api/v1
npm run dev
```

Frontend dev server runs on `http://localhost:5173`.

---

## Understanding the Docker networking (if you hit connection errors)

- Containers reach each other by **service name** (`db`, `redis`, `api`) —
  never `localhost`. `localhost` inside a container means that container
  itself, not your machine.
- Your browser/terminal on your actual machine reaches containers via
  `localhost` + the **published port** (`localhost:8000`, `localhost:5432`).
- `.env`'s `DATABASE_URL`/`REDIS_URL` are read by code running _inside_ the
  `api` container, so under Docker they must say `db`/`redis`, not
  `localhost`. If you're running the API natively (Option B above), the
  opposite is true — use `localhost` there instead.

| From...                        | Reach Postgres via | Reach Redis via  | Reach the API via |
| ------------------------------ | ------------------ | ---------------- | ----------------- |
| Another container (e.g. `api`) | `db:5432`          | `redis:6379`     | `api:8000`        |
| Your machine / browser         | `localhost:5432`   | `localhost:6379` | `localhost:8000`  |

---

## Environment variables (backend)

All read from `.env` via `app/core/config.py`. See `.env.example` for full
inline comments and setup walkthroughs (Gmail App Password, Twilio, etc.).

| Variable                                                                                           | Default                     | Notes                                                                                                            |
| -------------------------------------------------------------------------------------------------- | --------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URL`                                                                                     | _(required)_                | `db` for Docker, `localhost` for native                                                                          |
| `TEST_DATABASE_URL`                                                                                | _(optional)_                | Separate DB used only by the pytest suite                                                                        |
| `REDIS_URL`                                                                                        | `redis://localhost:6379/0`  | `redis` for Docker                                                                                               |
| `SECRET_KEY`                                                                                       | _(required)_                | Long random string, signs JWTs — generate your own                                                               |
| `ALGORITHM`                                                                                        | `HS256`                     | JWT signing algorithm                                                                                            |
| `ACCESS_TOKEN_EXPIRE_MINUTES`                                                                      | `60`                        |                                                                                                                  |
| `REFRESH_TOKEN_EXPIRE_DAYS`                                                                        | `7`                         |                                                                                                                  |
| `ENVIRONMENT`                                                                                      | `development`               | `production` suppresses tracebacks in error responses                                                            |
| `CORS_ORIGINS`                                                                                     | `["http://localhost:5173"]` | JSON array                                                                                                       |
| `SIGHTING_REPORT_RATE_LIMIT`                                                                       | `5/minute`                  | Per-user                                                                                                         |
| `FRONTEND_URL`                                                                                     | `http://localhost:5173`     | Used to build links in emails                                                                                    |
| `EMAIL_BACKEND`                                                                                    | `console`                   | `console` logs emails instead of sending; set `smtp` for real delivery                                           |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` / `SMTP_FROM_EMAIL` / `SMTP_USE_TLS` | —                           | Only used when `EMAIL_BACKEND=smtp`                                                                              |
| `SMTP_SENDING_DOMAIN`                                                                              | _(empty)_                   | Optional, only for providers with domain-level DKIM (SendGrid/Postmark/SES/Mailgun) — leave blank for Gmail SMTP |
| `SMS_BACKEND`                                                                                      | `console`                   | `console` logs the 2FA code instead of texting; set `twilio` for real SMS                                        |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_NUMBER`                                  | —                           | Only used when `SMS_BACKEND=twilio`                                                                              |
| `UPLOAD_DIR`                                                                                       | `uploads`                   | Where photos are stored, served at `/media`                                                                      |
| `MAX_UPLOAD_BYTES`                                                                                 | `5242880` (5MB)             |                                                                                                                  |
| `LOGIN_FAILURE_THRESHOLD` / `LOGIN_FAILURE_WINDOW_SECONDS` / `LOGIN_LOCKOUT_SECONDS`               | `5` / `900` / `900`         | Login lockout after repeated failures                                                                            |
| `EMERGENCY_CONTACTS`                                                                               | India-wide defaults         | JSON array, override for a different region                                                                      |

**Frontend** (`frontend/.env`): `VITE_API_BASE_URL` (default
`http://localhost:8000/api/v1`).

---

## Running migrations

```bash
# Docker
docker compose exec api alembic upgrade head

# Native
alembic upgrade head
```

To generate a new migration after changing a model:

```bash
alembic revision --autogenerate -m "describe the change"
# review the generated file in alembic/versions/ before applying
alembic upgrade head
```

---

## Running tests

Tests run against a real Postgres+PostGIS database (separate from dev data)
and real Redis — no mocking, so geo-search and rate-limiting are tested
against the same engine used in production. Each test runs inside a
transaction that's rolled back afterward (`app/tests/conftest.py`), so tests
never leave data behind or interfere with each other; Redis keys used for
rate limiting/refresh tokens/caching are flushed before and after every test.

```bash
# Docker
docker compose exec api pytest --cov=app --cov-report=term-missing

# Native
pytest --cov=app --cov-report=term-missing
```

> **First time only:** the test database (`mpn_test_db`) needs to exist with
> the PostGIS extension enabled. Under Docker, `scripts/init-test-db.sql`
> creates it automatically on a _fresh_ Postgres data volume. If that volume
> already has data, run manually:
>
> ```bash
> docker compose exec db psql -U mpn_user -d mpn_db -c "CREATE DATABASE mpn_test_db;"
> docker compose exec db psql -U mpn_user -d mpn_test_db -c "CREATE EXTENSION IF NOT EXISTS postgis;"
> ```
>
> (Native: run the equivalent `psql`/`createdb` commands directly against
> your local Postgres.)

Lint:

```bash
pip install -r requirements-dev.txt
ruff check app
```

Frontend lint:

```bash
cd frontend
npm run lint
```

---

## Building for production

```bash
cd frontend
npm run build     # outputs frontend/dist
npm run preview   # serve the production build locally to sanity-check it
```

Backend: run via the provided `Dockerfile`, or `uvicorn app.main:app` behind
a process manager (e.g. gunicorn with the uvicorn worker class) — set
`ENVIRONMENT=production` in `.env` so unhandled-exception responses don't
leak tracebacks.

---

## Access control summary

Full details, including the row-level "who can act on _this specific case_"
rules, are in `docs/SECURITY_AND_ACCESS.md`. Short version:

| Action                            |     Reporter     |               Authority (verified)               | Admin |
| --------------------------------- | :--------------: | :----------------------------------------------: | :---: |
| Create case                       |     ✅ (own)     |                        ✅                        |  ✅   |
| Edit case                         |     ✅ (own)     |                  ✅ (assigned)                   |  ✅   |
| Approve / dismiss case            |        ❌        | ✅ (station it was routed to, or unrouted cases) |  ✅   |
| Claim a case                      |        ❌        |                ✅ (if unclaimed)                 |  ✅   |
| Change case status                |        ❌        |             ✅ (assigned cases only)             |  ✅   |
| Share case with another authority |        ❌        |             ✅ (assigned cases only)             |  ✅   |
| Submit sighting                   | ✅ (+ anonymous) |                        ✅                        |  ✅   |
| Review sighting                   |        ❌        |          ✅ (cases they have access to)          |  ✅   |
| Approve authority accounts        |        ❌        |                        ❌                        |  ✅   |

Authority accounts require admin approval (`is_verified`) before they can
review sightings, approve/dismiss cases, or change case status — self-
registering as `role=authority` alone isn't enough.

---

## Design notes

- **Geo columns use PostGIS `geography(Point, 4326)`**, not separate
  lat/lng floats — enables `ST_DWithin` radius queries directly in SQL.
- **Cases route to one station**, not broadcast to every authority — see
  `case_service.create_case` / `_resolve_target_authority`. Unrouted cases
  (no station within range, or none has a jurisdiction set yet) stay open to
  any verified authority rather than becoming unreviewable.
- **`reported_by` on Sighting is nullable** — supports anonymous public tips.
- **`AuditLog` is append-only** — tracks who changed case status / reviewed
  sightings, important for a domain involving vulnerable people's data.
- **Native Postgres enums** (`user_role`, `case_status`, `sighting_status`)
  enforce valid values at the DB level, not just in application code.
- **`console` email/SMS backends by default** — the project runs fully
  out of the box with zero external accounts; real delivery is opt-in.

## Continuous Integration

`.github/workflows/ci.yml` runs on every push/PR: spins up Postgres+PostGIS
and Redis as service containers, lints with `ruff`, then runs the full
pytest suite with coverage (fails under 70% coverage). Coverage XML is
uploaded as a workflow artifact.
