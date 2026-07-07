# INVIGILO — Functional and Non-Functional Requirements

> Companion to `01-srs.md`. Every requirement has a stable ID (FR-x, NFR-x, AC-x) so it can be referenced from code, tests, and PRs. Phases 2+ will quote these IDs in commit messages and PR descriptions.

---

## 1. Functional requirements

The functional requirements are organised by module. The list is exhaustive for v1 — any item not in this catalogue is **not** in scope.

### 1.1 Authentication & identity (AUTH)

- **FR-AUTH-01** — Users authenticate with email and password. Email is the unique identifier.
- **FR-AUTH-02** — Authentication issues an access token (15-minute lifetime) and a refresh token (7-day lifetime, refresh-on-rotate).
- **FR-AUTH-03** — Logout invalidates the refresh token server-side; access tokens expire naturally.
- **FR-AUTH-04** — Forgot-password flow sends a one-time signed link (30-minute TTL) to the registered email.
- **FR-AUTH-05** — Reset-password consumes the link and accepts a new password that meets the password policy (see AC-AUTH-PWD).
- **FR-AUTH-06** — Email verification: new users must verify their email before any protected endpoint accepts requests from them.
- **FR-AUTH-07** — Change-password requires the current password and the new password; old password is verified, new password is hashed with Argon2id.
- **FR-AUTH-08** — Profile management: view and edit name, phone, avatar, and time-zone preference.
- **FR-AUTH-09** — Account lockout: 5 consecutive failed logins lock the account for 15 minutes and emit an audit event.
- **FR-AUTH-10** — All authentication events (login, logout, lockout, password change, password reset request/confirm) are written to the audit log.

### 1.2 User, role, and permission management (USR)

- **FR-USR-01** — System Administrators can create, read, update, and disable user accounts.
- **FR-USR-02** — A user may hold **multiple roles**; the effective permission set is the union.
- **FR-USR-03** — Roles are predefined for v1 (System Administrator, Examination Officer, Invigilator, Head of Department, Faculty Dean) and may not be created at runtime.
- **FR-USR-04** — Permissions are seed-managed (versioned migration); the database is the source of truth, the migration is the deployment record.
- **FR-USR-05** — Disabling a user (soft delete) revokes all refresh tokens and blocks future logins. Historical records (assignments, audit) are preserved.
- **FR-USR-06** — A user record carries: id, email, full name, phone, avatar, time zone, is_active, is_email_verified, is_staff, is_superuser, created_at, updated_at, last_login.

### 1.3 Academic structure (ACA)

- **FR-ACA-01** — **Faculty**: id, code, name, dean (FK to User, nullable until appointed), description.
- **FR-ACA-02** — **Department**: id, code, name, faculty (FK), head (FK to User, nullable), description.
- **FR-ACA-03** — **AcademicProgramme**: id, code, name, department (FK), duration_years, awarding_institution.
- **FR-ACA-04** — **Course**: id, programme (FK), code, name, level, credit_hours.
- **FR-ACA-05** — **Unit**: id, course (FK), code, name, credit_hours, semester, is_examinable (default true).
- **FR-ACA-06** — All academic entities support soft delete (`is_active`) and audit trail.
- **FR-ACA-07** — Department codes are unique within a faculty. Unit codes are unique within a course.

### 1.4 People (PER)

- **FR-PER-01** — **Student**: id, registration_number (unique), full_name, programme (FK), current_year, current_semester, email, phone, photo, is_active.
- **FR-PER-02** — **Invigilator**: id, user (FK, 1-to-1), employee_number (unique), department (FK), max_daily_assignments (default 3), max_weekly_assignments (default 10), is_available (default true), skills (text — comma-separated tags).
- **FR-PER-03** — Invigilators may declare **availability windows** per ExamPeriod: a set of (date, time-range) tuples when they cannot be assigned.
- **FR-PER-04** — Bulk import of students and invigilators from CSV is supported via the API and the UI.

### 1.5 Examination timetable (EXM)

- **FR-EXM-01** — **ExamPeriod**: id, name, semester, academic_year, starts_on, ends_on, is_active (only one may be active at a time).
- **FR-EXM-02** — **ExamSession**: id, exam_period (FK), unit (FK), session_date, starts_at, ends_at, expected_candidates (int), notes.
- **FR-EXM-03** — Two ExamSessions in the same ExamPeriod must not overlap in time if they share a candidate (enforced by trigger or service-level check on save).
- **FR-EXM-04** — Status lifecycle of an ExamSession: `draft` → `scheduled` → `in_progress` → `completed` → `archived`. Only `draft` and `scheduled` may be edited.
- **FR-EXM-05** — The expected_candidates count drives the **capacity rule** (1–50→1, 51–100→2, 101–150→3, 151+→4 invigilators per session).

### 1.6 Room management (ROM)

- **FR-ROM-01** — **ExamRoom**: id, code, name, building, floor, capacity, has_projector, has_cctv, is_accessible, is_active.
- **FR-ROM-02** — **RoomAllocation**: id, exam_session (FK), room (FK), allocated_capacity (int ≤ room.capacity). Uniqueness: a (date, time, room) may have at most one allocation.
- **FR-ROM-03** — The sum of allocated_capacity across RoomAllocations for a single ExamSession must equal the session's expected_candidates (or a configured split across rooms).

### 1.7 Smart invigilator allocation (ALC)

- **FR-ALC-01** — The allocator is invoked over a whole ExamPeriod and produces a deterministic set of `InvigilatorAssignment` rows.
- **FR-ALC-02** — **InvigilatorAssignment**: id, exam_session (FK), invigilator (FK), room (FK, nullable when session is unallocated), role (`lead` or `assistant`), assigned_at, assigned_by (FK to user, nullable for system-assigned), status (`assigned`, `accepted`, `declined`, `replaced`, `completed`).
- **FR-ALC-03** — Hard constraints (must hold):
  - C1. An invigilator is not assigned to two ExamSessions whose time intervals overlap.
  - C2. An invigilator is not assigned to two different rooms in the same ExamSession.
  - C3. An invigilator is not assigned outside their declared availability windows.
  - C4. The number of assignments per session respects the capacity rule.
- **FR-ALC-04** — Soft objectives (optimised, may be relaxed if infeasible):
  - O1. Fair workload distribution: minimise the variance of assignments per invigilator in the period.
  - O2. Department preference: prefer invigilators from the same department as the unit, where possible.
  - O3. Lead role rotation: vary who is the `lead` across consecutive sessions of the same invigilator.
- **FR-ALC-05** — The allocator is idempotent: re-running it on the same input with the same configuration produces the same assignments, *unless* existing assignments are explicitly cleared first.
- **FR-ALC-06** — The allocator writes assignments inside a single database transaction; partial failure rolls back the whole run.
- **FR-ALC-07** — The allocator is runnable as a Celery task and synchronously from a management command (`python manage.py allocate --period=<id>`).
- **FR-ALC-08** — Allocation progress and outcome are reported back to the caller (rows assigned, rows skipped, constraint violations).

### 1.8 Attendance (ATT)

- **FR-ATT-01** — **Attendance**: id, exam_session (FK), invigilator (FK), kind (`check_in` or `check_out`), at (timestamp), method (`qr`, `manual`, `pin`), location (text, optional), recorded_by (FK to user).
- **FR-ATT-02** — An invigilator may have at most one `check_in` and one `check_out` per session. The check-out must be after the check-in.
- **FR-ATT-03** — If a check-in is more than 15 minutes after the session's start time, the attendance row is flagged `late` (boolean on the row).
- **FR-ATT-04** — A 6-digit PIN is generated per (session, invigilator) pair and may be used as a fallback check-in method when QR scanning is unavailable.
- **FR-ATT-05** — Attendance is viewable in real time on the EO dashboard.

### 1.9 Incident reporting (INC)

- **FR-INC-01** — **IncidentReport**: id, exam_session (FK), room (FK), reporter (FK to User), category (`misconduct`, `late_arrival`, `cheating`, `medical`, `missing_script`, `other`), description, occurred_at, status (`open`, `investigating`, `resolved`, `closed`), resolved_by (FK), resolved_at, resolution_notes.
- **FR-INC-02** — Incidents support **evidence uploads** (images, PDFs) up to 10 MB per file, stored in a media bucket.
- **FR-INC-03** — Incidents are immutable once `closed`; further actions are recorded as audit events.

### 1.10 Notifications (NOT)

- **FR-NOT-01** — **Notification**: id, user (FK), kind (`assignment`, `schedule`, `attendance`, `incident`, `system`), title, body, link, read_at (nullable), created_at.
- **FR-NOT-02** — A dashboard notification list is fetched on every page load (server component) and via a polling endpoint every 30 seconds.
- **FR-NOT-03** — Email notifications are sent for: assignment creation, assignment reminder (24h and 1h before session), schedule change, incident opened against the invigilator.
- **FR-NOT-04** — Email delivery is asynchronous (Celery); failures are retried up to 3 times with exponential backoff.

### 1.11 Reports and exports (RPT)

- **FR-RPT-01** — Built-in reports:
  - **RPT-01** — Daily Examination Report (sessions, rooms, invigilators, attendance).
  - **RPT-02** — Attendance Report (per invigilator and per session).
  - **RPT-03** — Room Utilization Report (capacity vs allocated, by period).
  - **RPT-04** — Invigilator Workload Report (assignments per person, per period).
  - **FR-RPT-05** — Department Report (sessions and incidents per department).
  - **RPT-06** — Incident Report.
- **FR-RPT-02** — Each report can be exported as **PDF** (ReportLab) and **Excel** (OpenPyXL); tabular reports also export **CSV**.
- **FR-RPT-03** — Exports are generated asynchronously for large reports (>1000 rows) and downloadable from a "Reports" page when ready.

### 1.12 Analytics dashboard (ANL)

- **FR-ANL-01** — The dashboard surfaces, on a single page:
  - Today's examination count and list.
  - Today's invigilator assignments.
  - Attendance summary (checked-in, late, absent).
  - Room utilisation (sessions ÷ available rooms).
  - Upcoming exams (next 7 days).
  - Incident statistics (open, resolved, by category).
  - Faculty and department breakdowns (cards with KPIs).
- **FR-ANL-02** — Charts are rendered on the client (Recharts); data is fetched from a single `GET /api/analytics/overview` endpoint.
- **FR-ANL-03** — All counts are scoped to the current ExamPeriod and to the caller's role (an HOD sees only their department).

### 1.13 Audit logs (AUD)

- **FR-AUD-01** — **AuditLog**: id, actor (FK to User, nullable for system), action (string), target_type, target_id, metadata (JSONB), ip_address, user_agent, created_at.
- **FR-AUD-02** — Audit rows are **append-only** — no API endpoint updates or deletes them.
- **FR-AUD-03** — The audit log is searchable by actor, action, target, and date range.

### 1.14 System settings (SET)

- **FR-SET-01** — **SystemSetting**: key (unique), value (JSONB), description, updated_by, updated_at.
- **FR-SET-02** — Keys are seed-managed and read by services at runtime (e.g. `allocator.max_daily_assignments_default`, `attendance.late_threshold_minutes`).

---

## 2. Non-functional requirements

Non-functional requirements use the **ISO/IEC 25010** quality model. Each requirement is testable.

### 2.1 Performance efficiency

- **NFR-PE-01** — p95 latency for any list endpoint (`GET /api/<resource>/`) under 500 records is ≤ 200 ms on a 2 vCPU / 4 GB database.
- **NFR-PE-02** — p95 latency for single-record detail endpoints is ≤ 100 ms.
- **NFR-PE-03** — Allocation run for a 4-week ExamPeriod with 1,000 sessions and 200 invigilators completes in ≤ 60 s.
- **NFR-PE-04** — Dashboard initial render (TTI) under 3 s on a 4G connection.
- **NFR-PE-05** — Database queries are bounded: no list endpoint scans the full table; every list endpoint is paginated and indexed.

### 2.2 Security

- **NFR-SE-01** — Passwords are hashed with **Argon2id** (memory 64 MB, iterations 3, parallelism 4).
- **NFR-SE-02** — All API endpoints (except `/api/auth/*` and `/api/health`) require a valid JWT.
- **NFR-SE-03** — Authorization is enforced server-side; the frontend never gates API access alone.
- **NFR-SE-04** — CSRF is enabled for session-authenticated routes; JWT routes use bearer auth.
- **NFR-SE-05** — CORS is allow-listed by origin; the allow-list is read from environment.
- **NFR-SE-06** — Rate limiting: 5 login attempts per minute per IP; 100 anonymous API calls per minute per IP; 1000 authenticated calls per minute per user.
- **NFR-SE-07** — Input validation: every request body is validated by a DRF serializer with explicit field types and constraints.
- **NFR-SE-08** — Audit log captures every create/update/delete of a security- or business-critical entity.
- **NFR-SE-09** — No secrets in version control; `.env` files are `.gitignore`d; production secrets come from a secret manager.

### 2.3 Scalability

- **NFR-SC-01** — Stateless application tier: any number of backend instances may run behind a load balancer.
- **NFR-SC-02** — Celery workers can be scaled horizontally; the allocator is the only long-running task in v1.
- **NFR-SC-03** — Database is the bottleneck, not the application; the schema is normalised to 3NF with explicit indexes (see `05-erd.md`).

### 2.4 Reliability

- **NFR-RE-01** — System uptime target: 99.5 % during an active ExamPeriod (measured monthly).
- **NFR-RE-02** — All write operations on business-critical entities are transactional.
- **NFR-RE-03** — Database backups are taken nightly, retained 30 days, restorable to a point in time within 1 hour.
- **NFR-RE-04** — Email delivery is idempotent (a delivery record is written and the same record is updated, not duplicated).

### 2.5 Usability

- **NFR-US-01** — Dark mode and light mode are both supported and persist per user.
- **NFR-US-02** — Layout is responsive: usable on a 1280-px laptop down to a 360-px phone.
- **NFR-US-03** — Forms provide inline validation; submission errors are visible within 1 second of blur.
- **NFR-US-04** — Skeleton loaders are shown for any list fetching > 200 ms.
- **NFR-US-05** — Destructive actions (delete, force reallocate) require a typed confirmation.

### 2.6 Maintainability

- **NFR-MA-01** — Backend follows the layout in `06-folder-structure.md`; no cross-app imports between business apps.
- **NFR-MA-02** — Test coverage target: ≥ 80 % on the `accounts`, `allocator`, `attendance`, and `incidents` apps.
- **NFR-MA-03** — Linting: `ruff` and `black` on the backend; `eslint` and `prettier` on the frontend; both run in CI.
- **NFR-MA-04** — Type safety: `mypy --strict` on the backend (excluding third-party migrations); TypeScript `strict: true` on the frontend.
- **NFR-MA-05** — Every public API endpoint is documented in OpenAPI 3.0 (drf-spectacular) and reachable at `/api/schema/` and `/api/docs/`.

### 2.7 Compatibility

- **NFR-CO-01** — Latest two stable versions of Chrome, Edge, Firefox, Safari.
- **NFR-CO-02** — Latest two stable versions of iOS Safari and Chrome on Android.
- **NFR-CO-03** — Python 3.13; PostgreSQL 16.

### 2.8 Compliance

- **NFR-CP-01** — Personal data handling follows the institution's data-protection policy. A privacy notice is shown at first login.
- **NFR-CP-02** — Audit log retention: minimum 1 year, maximum 7 years (configurable).
- **NFR-CP-03** — Evidence uploads are stored encrypted at rest (S3 SSE or filesystem `gpg`).

---

## 3. Acceptance criteria

Acceptance criteria are the gate for "done". A milestone is complete only when every AC referenced by the milestone's modules passes.

### 3.1 Authentication

- **AC-AUTH-01** — A new user can register, receive a verification email, click the link, and log in.
- **AC-AUTH-02** — Logging in returns an access token and a refresh token; the access token is accepted on subsequent calls; the refresh token can be exchanged for a new access token.
- **AC-AUTH-03** — Five wrong passwords in 60 seconds lock the account; an admin can unlock it.
- **AC-AUTH-PWD** — Passwords are ≥ 12 characters and contain at least three of: lowercase, uppercase, digit, symbol.

### 3.2 Allocation

- **AC-ALC-01** — Given 100 sessions and 30 invigilators, the allocator assigns every session a number of invigilators matching the capacity rule, with no invigilator double-booked.
- **AC-ALC-02** — If the inputs are infeasible (too few invigilators), the allocator returns a structured error with the list of under-staffed sessions and exits with non-zero status.
- **AC-ALC-03** — Re-running the allocator on the same inputs yields the same assignments (idempotence), unless the user explicitly clears them first.
- **AC-ALC-04** — Workload variance across invigilators is minimised to within 1 assignment of the mean, where possible.

### 3.3 Attendance and incidents

- **AC-ATT-01** — Check-in and check-out for the same (session, invigilator) appear on the EO dashboard within 5 seconds.
- **AC-INC-01** — Submitting an incident with an evidence file writes both the report and a media record; the report is visible to the EO immediately.

### 3.4 Reports

- **AC-RPT-01** — Each of the six named reports renders to a downloadable PDF and Excel file with the same row counts as the on-screen table.
- **AC-RPT-02** — Exports > 1,000 rows complete in the background; a notification appears on completion with a download link.

---

## 4. Out of scope (v1)

- Multi-tenant SaaS.
- Native mobile apps.
- Live video proctoring.
- Payment processing.
- A student-facing portal (students are imported; they do not log in for v1).
- AI-based anomaly detection on incidents (analytics are descriptive only in v1).
