# Frontend — Reunification Network

React (Vite) frontend for the Missing Persons & Reunification Network API.

## Status: first pass

Built so far:
- Auth: register (reporter or authority), log in, log out, session restore on reload
- Case browsing with status filter chips, case detail page
- Case creation form with an interactive map for the last-seen location
- Sighting submission form (works for anonymous or logged-in users) with a map picker
- Case claim + status-change controls, shown inline on the case detail page for
  verified authorities/admins (no separate dashboard yet — see below)

**Not built yet** (see `docs/FEATURE_TICKET_LIST.md`, "Frontend" section):
- A dedicated authority review queue / dashboard (TICKET-606) — for now,
  authorities work case-by-case from each case's detail page
- A dedicated admin dashboard for authority approvals (TICKET-607) — the
  backend endpoint exists (`/api/v1/admin/authority-requests`) but there's no
  UI for it yet
- Nearby-search UI (the backend `/cases/nearby` and `/sightings/nearby`
  endpoints exist and are used nowhere in the frontend yet)

## Setup

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Runs at `http://localhost:5173`. Make sure the backend is running
(`docker compose up` from the project root) at `http://localhost:8000` —
`VITE_API_BASE_URL` in `.env` points there by default, and the backend's
`CORS_ORIGINS` already allows `http://localhost:5173` out of the box.

## How auth works here

- Access + refresh tokens are stored in `localStorage` (see `src/api/client.js`).
  **Tradeoff, worth knowing:** `localStorage` is readable by any JS running on
  the page, so it's vulnerable to token theft via XSS in a way an
  `httpOnly` cookie wouldn't be. This is a reasonable choice for a portfolio
  project talking to your own API, but if this went to production, moving
  refresh-token storage to an `httpOnly` cookie (with the backend setting it)
  would be the upgrade — noted here rather than silently picked for you.
- `src/api/client.js`'s response interceptor catches `401`s, calls
  `/api/v1/auth/refresh` once (de-duplicated across concurrent failures), and
  retries the original request. If refresh itself fails, tokens are cleared
  and the user is treated as logged out.
- `src/context/AuthContext.jsx` calls `GET /api/v1/auth/me` on load to
  identify who's logged in from a stored token — this endpoint didn't exist
  before this frontend pass; it was added to the backend
  (`app/api/v1/auth.py`) since there was no other way to recover the user's
  role after a page reload.

## A backend bug this pass caught

Building the registration form surfaced a real privilege-escalation issue:
`UserCreate.role` previously accepted any `UserRole`, including `admin`, with
no verification gate on the admin role the way authority accounts have
`is_verified`. Anyone could have POSTed `role: "admin"` to `/auth/register`
and gotten full admin access immediately. Fixed in
`app/schemas/user.py`/`app/services/auth_service.py` (role is now a
`Literal["reporter", "authority"]` — admin accounts aren't self-registerable
at all), with a regression test added in `app/tests/test_auth.py`.

## Project layout

```
frontend/
├── src/
│   ├── api/            # axios client + one module per resource
│   ├── context/         # AuthContext (session state, login/register/logout)
│   ├── components/       # Masthead, CaseCard, StatusBadge, SightingForm,
│   │                      LocationPicker, ProtectedRoute
│   ├── pages/             # one file per route
│   ├── styles/index.css   # design tokens + all styling (no CSS framework)
│   ├── App.jsx             # routes
│   └── main.jsx
├── package.json
└── vite.config.js
```

## Design notes

Palette and type are calm and civic on purpose (cool ink/slate/cloud, serif
headings + sans body) — this is a registry for missing people, not a
consumer app, so the direction deliberately avoids anything that reads as
alarmist or salesy. The one recurring signature element is the diagonal
"status ribbon" in the corner of each case card (`.status-ribbon` in
`index.css`) — a quiet nod to a flyer pinned to a community board, color-keyed
to case status (open/lead found/resolved) so status is scannable across a
whole grid of cases at a glance.
