# Project Requirements

## 1. Overview

A platform for registering missing person cases, collecting public sighting
reports, and coordinating verification/follow-up by authorities (police
departments, NGOs). Built as an SDE portfolio project demonstrating backend
architecture, auth/RBAC, geo-queries, rate limiting, and CI/CD practices.

## 2. User roles

| Role | Description |
|---|---|
| **Public Reporter** | Any registered user. Can create missing person cases and submit sighting reports. |
| **Verified Authority** | Police department or NGO account, approved by an admin. Can review sightings, verify/dismiss them, and update case status. |
| **Super Admin** | Approves authority accounts, has full visibility, can moderate any content. |

## 3. Functional requirements

### 3.1 Case management
- FR-1: A reporter can create a case with: name, photo, age at disappearance, last-seen location (geo point + address), description, last-seen date/time.
- FR-2: A reporter can view/edit cases they created (before an authority takes ownership).
- FR-3: An authority can claim a case, updating `assigned_authority_id`.
- FR-4: An authority can change case status: `Open → Lead Found → Resolved`. Status changes are logged in the audit trail.
- FR-5: Anyone (including unauthenticated visitors) can search/browse open cases.

### 3.2 Sighting reports
- FR-6: Any user (authenticated or anonymous) can submit a sighting report against a case: location, description, optional photo.
- FR-7: Sighting submission is rate-limited per IP/user to prevent spam (see SECURITY_AND_ACCESS.md).
- FR-8: An authority can review a sighting and mark it `Verified` or `Dismissed`.
- FR-9: Verifying a sighting can optionally trigger a case status update to `Lead Found`.

### 3.3 Geo-search
- FR-10: Given a location and radius, return sightings within that radius, ordered by distance.
- FR-11: Given a location and radius, return open cases whose last-seen location falls within that radius.

### 3.4 Auth & accounts
- FR-12: Users register with email/password; passwords are hashed (never stored plaintext).
- FR-13: Authority accounts require admin approval (`is_verified = true`) before they can review sightings or update case status.
- FR-14: JWT access + refresh token flow.

### 3.5 Admin
- FR-15: Admin can list pending authority account requests and approve/reject them.
- FR-16: Admin can view audit logs for any case or sighting.

## 4. Non-functional requirements

- NFR-1: **Availability** — health check endpoint for uptime monitoring.
- NFR-2: **Rate limiting** — public endpoints (especially sighting submission) protected against abuse via Redis-backed limits.
- NFR-3: **Auditability** — every state-changing action by an authority/admin is recorded in an append-only audit log.
- NFR-4: **Data sensitivity** — this domain involves vulnerable people; case/sighting data should not be exposed beyond what's needed (e.g., contact details of reporters are never shown to the public).
- NFR-5: **Testability** — core business logic (case/sighting services) covered by pytest; CI runs on every push via GitHub Actions.
- NFR-6: **Performance** — geo-search queries should use PostGIS spatial indexes, not application-level distance calculation.

## 5. Out of scope (for this portfolio version)

- SMS/push notifications to reporters when a case is updated
- Multi-language support
- Mobile app (web-responsive React only)
- Payment/donation processing
