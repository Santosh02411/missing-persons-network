# Security & Access Control

## Authentication

- JWT access tokens (short-lived, `ACCESS_TOKEN_EXPIRE_MINUTES`, default 60 min)
  + refresh tokens (`REFRESH_TOKEN_EXPIRE_DAYS`, default 7 days).
- Passwords hashed with bcrypt (via `passlib`) — never stored or logged in plaintext.
- Tokens signed with `SECRET_KEY` (HS256) — must be a long random value in
  production, set via environment variable, never committed.

## RBAC matrix

| Action | Reporter | Authority (verified) | Admin |
|---|:---:|:---:|:---:|
| Create case | ✅ (own) | ✅ | ✅ |
| Edit case | ✅ (own, before claimed) | ✅ (assigned) | ✅ |
| Change case status | ❌ | ✅ (assigned cases) | ✅ |
| Submit sighting | ✅ | ✅ | ✅ |
| Review/verify/dismiss sighting | ❌ | ✅ | ✅ |
| View audit logs | ❌ | own actions only | ✅ (all) |
| Approve authority accounts | ❌ | ❌ | ✅ |

Enforcement happens via a `require_role()` FastAPI dependency (Phase 3) applied
per-route, plus row-level checks in the service layer (e.g., a reporter can only
edit a case where `case.created_by == current_user.id`).

## Authority account verification

Authority accounts are not self-service-trusted: registering with `role=authority`
sets `is_verified=False` until an admin approves. Unverified authority accounts
can browse but cannot review sightings or change case status — this prevents
someone from just self-declaring as police/NGO to gain elevated access.

## Rate limiting

- Redis-backed, applied per-route.
- Sighting submission: tightest limit (`SIGHTING_REPORT_RATE_LIMIT`, default
  5/minute) since it's the most abuse-prone public write endpoint.
- Keyed by authenticated user ID when logged in, IP address for anonymous requests.
- Returns HTTP 429 with a `Retry-After` header.

## Data protection considerations

This domain involves potentially vulnerable people (missing persons, their
families, anonymous tipsters), so:

- Reporter/tipster identity is never exposed to the public — only to
  authorities reviewing the case, and only as needed.
- Audit logs record every status change and review decision (who, when, what
  changed) for accountability, but are only visible to admins (own actions
  visible to the acting authority).
- No case or sighting is ever hard-deleted by a non-admin — status transitions
  and soft-delete flags preserve history rather than erasing it.

## Transport & infra

- HTTPS required in production (terminated at a reverse proxy/load balancer —
  out of scope for this repo, but documented as a deployment requirement).
- CORS restricted to known frontend origins via `CORS_ORIGINS` setting — not `*`.
- DB credentials, JWT secret, and Redis URL all supplied via environment
  variables (`.env`, excluded from git via `.gitignore`), never hardcoded.

## Known gaps (acceptable for portfolio scope, called out for transparency)

- No email verification flow yet for reporter accounts.
- No file-type/size validation spec yet for photo uploads (planned for Phase 2
  schema work — should restrict to image MIME types, reasonable size cap, and
  ideally virus-scan before storage).
- No account lockout/backoff on repeated failed logins yet — worth adding
  alongside Phase 3 auth work.
