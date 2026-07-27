# Project Workflow

## Build phases

This project is being built in five sequential phases:

| Phase | Scope | Status |
|---|---|---|
| 1 | Architecture & DB schema | ✅ Done |
| 2 | API endpoint design (routes, request/response models) | ✅ Done |
| 3 | Auth/RBAC implementation (JWT, role enforcement) | ⏳ Next |
| 4 | Geo-search + Redis rate limiting | Not started |
| 5 | Testing (pytest) + CI/CD (GitHub Actions) | Not started |

Each phase produces working, runnable code — not just design docs. See
[FEATURE_LOG.md](./FEATURE_LOG.md) for what's shipped and
[FEATURE_TICKET_LIST.md](./FEATURE_TICKET_LIST.md) for the ticket-level backlog.

## Git workflow

- `main` — always deployable.
- Feature branches: `phase-2/api-routes`, `phase-3/auth-rbac`, etc., or
  finer-grained `feat/case-crud`, `feat/sighting-review` if you want per-ticket branches.
- Commit messages: `feat:`, `fix:`, `chore:`, `docs:`, `test:` prefixes (Conventional Commits),
  e.g. `feat(cases): add geo-indexed last_seen_location column`.
- Open a PR per phase (or per ticket), even solo — gives you a clean diff history
  to point to in interviews, and is where the GitHub Actions CI (Phase 5) will gate merges.

## Local dev loop

1. `docker compose up --build` — starts Postgres+PostGIS, Redis, API.
2. `docker compose exec api alembic upgrade head` — apply migrations.
3. Make changes, hit `http://localhost:8000/docs` for the auto-generated OpenAPI UI.
4. `docker compose exec api pytest` (once Phase 5 lands) before pushing.

## Adding a new model/migration

1. Add/edit the SQLAlchemy model in `app/models/`.
2. Import it in `app/db/base.py` if it's new.
3. `docker compose exec api alembic revision --autogenerate -m "description"`.
4. **Review the generated migration** — autogenerate doesn't always get enum
   changes or index details right.
5. `docker compose exec api alembic upgrade head`.

## Picking this project back up later

Read [MEMORY.md](./MEMORY.md) first — it's a condensed project-context summary
meant to be pasted into a new AI chat (or re-read yourself) to resume without
re-explaining the whole project.
