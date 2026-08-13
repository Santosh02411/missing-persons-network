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
| Claim a case | ❌ | ✅ (if unclaimed) | ✅ |
| Change case status | ❌ | ✅ (assigned cases only) | ✅ |
| Submit sighting | ✅ | ✅ | ✅ |
| Review/verify/dismiss sighting | ❌ | ✅ (cases they have access to) | ✅ |
| Share case with another authority | ❌ | ✅ (assigned cases only) | ✅ |
| Dismiss case | ❌ | ✅ (pending or assigned cases) | ✅ |
| View audit logs | ❌ | own actions only | ✅ (all) |
| Approve authority accounts | ❌ | ❌ | ✅ |

**Implemented** (Phase 3) via `app/core/deps.py`:
- `require_role(*roles)` — 403s unless the caller's role is in the allowed set.
- `require_verified_authority_or_admin` — stricter: also blocks an authority
  account that hasn't been approved yet (`is_verified=False`).
- Row-level checks live in the service layer, not the dependency — e.g.
  `case_service.update_case_status()` checks that the caller is *this case's*
  `assigned_authority_id` (or admin), not just "some authority." Role
  dependencies answer "is this kind of action allowed for this role at all";
  service-layer checks answer "is it allowed on *this specific row*."
- Sighting review is scoped to case access, same as case status changes: an
  authority can only review a sighting on a case they're the assigned
  authority for, or a collaborator on (`case_service.has_case_access`) — see
  `sighting_service.review_sighting` and `list_pending_sightings`. A station
  can't approve or dismiss sightings on a case routed to a different station.
  A case with no assigned authority yet (unclaimed) stays open to any
  verified authority, matching the same fallback used for unrouted cases at
  approval time.

## Authority account verification

Authority accounts are not self-service-trusted: registering with `role=authority`
sets `is_verified=False` until an admin approves. Unverified authority accounts
can browse but cannot review sightings or change case status — this prevents
someone from just self-declaring as police/NGO to gain elevated access.

## Refresh token rotation

Implemented in Phase 3: each call to `/api/v1/auth/refresh` issues a brand
new access+refresh pair and invalidates the previous refresh token. The
valid token's `jti` (a random ID embedded in the JWT) is tracked in Redis,
keyed by user ID with a TTL matching the token's own expiry. If a refresh
token is presented whose `jti` doesn't match what's stored — e.g. an old,
already-rotated token being replayed, a sign of possible token theft — the
whole session is revoked and the user must log in again rather than the
request just failing quietly. `POST /api/v1/auth/logout` revokes the stored
`jti` directly. Redis is doing double duty here and in Phase 4 (rate
limiting/caching) — same client, different key prefixes.

## Login lockout

Redis fixed-window failure counter, keyed by the *email being attempted*
(not user id, so failed attempts against nonexistent emails are tracked too
without a different response leaking account existence). After
`LOGIN_FAILURE_THRESHOLD` (default 5) failures within
`LOGIN_FAILURE_WINDOW_SECONDS` (default 15 min), the email is locked for
`LOGIN_LOCKOUT_SECONDS` (default 15 min) — `429` with `Retry-After`. A
successful login clears the counter.

## Password reset

`POST /auth/forgot-password` always returns the same generic response
whether or not the email is registered — this is deliberate, to prevent
using the endpoint to enumerate which emails have accounts. Reset tokens
live in Redis for 1 hour. `POST /auth/reset-password` consumes the token and
also revokes the user's existing refresh session — a stolen session
shouldn't survive a password change.

## Email verification

Separate from `is_verified` (which gates authority permissions) — tracks
whether the account's email has been confirmed via an emailed link.
**Deliberately doesn't block login or any action.** This project has no
real email provider configured (`core/email.py` just logs instead of
sending), so gating access on email confirmation would risk locking people
out with no way to actually receive the link. The frontend shows a banner
prompting verification instead.

## Photo uploads

`POST /api/v1/uploads/photo` requires auth, validates content-type
(`image/jpeg`/`png`/`webp` only) and streams the file in chunks to enforce a
size cap (`MAX_UPLOAD_BYTES`, default 5MB) without loading the whole file
into memory first. Filenames are always server-generated (random UUID),
never derived from the client-supplied filename. Served back via a
`StaticFiles` mount at `/media/` — not behind auth, since case/sighting
photos are meant to be publicly viewable once attached to a case.

## Rate limiting

**Implemented** (Phase 4) in `app/core/rate_limit.py`:
- Fixed-window counter via Redis `INCR` + `EXPIRE`, applied to
  `POST /api/v1/sightings` via `sighting_rate_limiter`.
- Keyed by `user:{id}` when authenticated, `ip:{client_host}` otherwise —
  anonymous tips are a real requirement here (FR-6), so the limiter can't
  just require auth.
- Enforces `SIGHTING_REPORT_RATE_LIMIT` (default `5/minute`) from settings.
- Returns HTTP `429` with a `Retry-After` header set from the key's actual
  Redis TTL.
- **Known tradeoff:** fixed-window (not sliding-window or token-bucket)
  allows a short burst right at a window boundary (e.g. 5 requests just
  before a minute rolls over, then 5 more right after). Acceptable for this
  portfolio's scope; a token-bucket approach (e.g. the `limits` library)
  would be the production-grade upgrade if that boundary case mattered.

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
