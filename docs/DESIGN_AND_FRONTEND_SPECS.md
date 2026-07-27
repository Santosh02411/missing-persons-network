# Design & Frontend Specs

> Frontend build starts in Phase 2+. This doc specs it ahead of time so the API
> design (Phase 2) matches what the UI will actually need.

## Pages

| Route | Access | Purpose |
|---|---|---|
| `/` | Public | Landing page, search bar, recently added open cases |
| `/cases` | Public | Browse/filter open cases (by location, status, date) |
| `/cases/:id` | Public | Case detail — photo, description, last-seen info, map, "Report a sighting" CTA |
| `/cases/new` | Reporter (auth) | Case creation form |
| `/cases/:id/edit` | Reporter (owner) | Edit own case |
| `/sightings/new/:caseId` | Public (auth optional) | Submit a sighting report against a case |
| `/dashboard/authority` | Authority | Queue of pending sightings to review, assigned cases |
| `/dashboard/admin` | Admin | Pending authority approvals, audit log viewer |
| `/login`, `/register` | Public | Auth |

## Key components

- **CaseCard** — photo thumbnail, name, last-seen location, status badge, age.
- **CaseMap** — Leaflet/Mapbox map showing last-seen point ± nearby verified sightings.
- **SightingForm** — location picker (map click or geolocation), description, optional photo upload.
- **StatusBadge** — color-coded: Open (blue), Lead Found (amber), Resolved (green).
- **ReviewQueueItem** (authority dashboard) — sighting summary + Verify/Dismiss buttons.
- **RoleGate** — wrapper component that hides/shows children based on the logged-in user's role, mirroring backend RBAC.

## UX notes

- Case submission and sighting reporting should work without requiring login
  for the sighting side (anonymous tips matter for this domain) — but flag
  anonymous submissions differently in the authority review queue.
- Rate-limit errors (429) should show a clear, non-alarming message ("You've
  submitted several reports recently — please wait a few minutes") rather than
  a raw error.
- Case photos and descriptions should be presented respectfully — this is
  sensitive subject matter involving real families.

## Visual direction

- Calm, trustworthy palette (blues/neutrals) — avoid anything that reads as
  alarmist or sensationalized given the subject matter.
- Clear visual hierarchy: case photo + name + status are the primary scan
  targets on any card/list view.
- Accessible contrast ratios (WCAG AA minimum) given this may be used by a
  wide range of users, including under stress.

## State management

- React Query (TanStack Query) for server state (cases, sightings) — fits
  naturally with FastAPI's REST endpoints and gives caching/invalidation for free.
- Local component state for form inputs; no global client-state library needed
  at this scale.
