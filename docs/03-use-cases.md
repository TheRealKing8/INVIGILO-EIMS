# INVIGILO — Use Cases and Role-Permission Matrix

> Companion to `01-srs.md` and `02-requirements.md`. Actors are the five user classes from §2.4 of the SRS. Every use case is referenced by a stable ID (UC-x) that maps to one or more functional requirements in `02-requirements.md`.

---

## 1. Actor profiles

### 1.1 System Administrator (SA)
- **Goal** — keep the platform operational, secure, and correctly configured.
- **Volume** — 1–3 per institution.
- **Tools** — full admin console, audit log access, system settings.
- **Constraints** — does not normally create examination content; their focus is users, roles, settings, and integrity.

### 1.2 Examination Officer (EO)
- **Goal** — produce a complete, fair invigilation schedule for every exam period.
- **Volume** — 1–5 per institution.
- **Tools** — timetable builder, allocation engine, attendance dashboard, reports.
- **Constraints** — cannot create users or change system settings.

### 1.3 Invigilator (IN)
- **Goal** — know where to be, when, and report what happens.
- **Volume** — 50–1,000 per institution.
- **Tools** — personal schedule, check-in/check-out, incident report form, profile.
- **Constraints** — sees only their own assignments; can only report incidents for sessions they are assigned to.

### 1.4 Head of Department (HOD)
- **Goal** — ensure their department is adequately staffed and the schedule is fair.
- **Volume** — 1 per department.
- **Tools** — departmental reports, invigilator roster, leave/availability approvals.
- **Constraints** — read-only on sessions outside their department; can propose (not impose) schedule changes.

### 1.5 Faculty Dean (DEA)
- **Goal** — faculty-level oversight and cross-department comparison.
- **Volume** — 1 per faculty.
- **Tools** — faculty roll-up reports, KPIs, incident trends.
- **Constraints** — read-only on operational data; can drill down into a department.

---

## 2. Use case catalogue

Each use case is given in the standard form: **actor · precondition · main flow · postcondition · exceptions**. Only the most consequential are listed; the rest are tracked in the GitHub issue tracker.

### 2.1 Authentication and identity

- **UC-01 — Log in** (any user)
  - *Pre:* the user has a verified account and is not locked.
  - *Flow:* enter email + password → submit → receive access + refresh tokens → land on dashboard.
  - *Post:* a session exists; an audit row is written.
  - *Ex:* wrong credentials (401), locked account (423), unverified email (403).

- **UC-02 — Log out** (any user)
  - *Pre:* user has a valid refresh token.
  - *Flow:* POST `/api/auth/logout` with refresh token → server invalidates the refresh row → access token is discarded by the client.
  - *Post:* refresh token cannot be used again; audit row written.

- **UC-03 — Forgot / reset password** (any user)
  - *Pre:* user has a registered email.
  - *Flow:* enter email → receive link → click link → set new password → success page.
  - *Post:* password is updated; old refresh tokens are invalidated.
  - *Ex:* email not found (return success silently to avoid enumeration), link expired (400).

- **UC-04 — Verify email** (any user)
  - *Pre:* user has registered but not yet verified.
  - *Flow:* click link in email → server marks email as verified → user can now log in.
  - *Post:* `is_email_verified` is true; audit row written.

- **UC-05 — Change password** (any authenticated user)
  - *Pre:* user knows current password.
  - *Flow:* enter current + new password → submit → server re-hashes → success.
  - *Post:* new password is in effect; all other refresh tokens are invalidated.

- **UC-06 — Manage own profile** (any user)
  - *Pre:* user is authenticated.
  - *Flow:* view profile → edit name, phone, avatar, time zone → save.
  - *Post:* profile is updated; audit row written.

### 2.2 User administration

- **UC-10 — Create user** (SA)
  - *Pre:* SA is authenticated.
  - *Flow:* open Users → fill form (email, name, role[s]) → submit → server creates user with random password and emails a verification + set-password link.
  - *Post:* user exists, is_active, has roles; audit row written.

- **UC-11 — Disable user** (SA)
  - *Pre:* user exists, is not the SA's own account.
  - *Flow:* open user → click "Disable" → confirm → server sets `is_active=false` and invalidates refresh tokens.
  - *Post:* user can no longer log in; historical records preserved.

- **UC-12 — Assign role** (SA)
  - *Pre:* user exists; role is seed-defined.
  - *Flow:* open user → toggle role → save → effective permission set updates immediately.
  - *Post:* new role is attached; audit row written.

### 2.3 Academic setup

- **UC-20 — Create faculty** (SA)
  - *Pre:* none.
  - *Flow:* enter code, name → save → optionally assign a dean.
  - *Post:* faculty is active and appears in selectors.

- **UC-21 — Create department** (SA)
  - *Pre:* faculty exists.
  - *Flow:* enter code, name, faculty → save → optionally assign a HOD.
  - *Post:* department is active and appears in selectors.

- **UC-22 — Create programme, course, unit** (SA, EO)
  - *Pre:* parent entity exists.
  - *Flow:* enter code, name, parent → save.
  - *Post:* entity is active; appears in selectors.

- **UC-23 — Bulk import students** (SA, EO)
  - *Pre:* CSV file with the right columns.
  - *Flow:* upload file → server validates → preview issues → confirm → server creates rows.
  - *Post:* students are created; a per-row error report is downloadable.

- **UC-24 — Bulk import invigilators** (SA, EO)
  - *Pre:* CSV file.
  - *Flow:* upload → validate → confirm → create users (with random password + verification email) and Invigilator rows.
  - *Post:* invigilators are active; their first login forces a password change.

### 2.4 Examination period and sessions

- **UC-30 — Create exam period** (EO)
  - *Pre:* none.
  - *Flow:* enter name, semester, dates → save.
  - *Post:* period is `draft`. Only one period may be `is_active` at a time; activating one deactivates the others.

- **UC-31 — Create exam session** (EO)
  - *Pre:* exam period is `active`; unit is examinable.
  - *Flow:* enter unit, date, start, duration, expected candidates → save.
  - *Post:* session is `draft`. Conflict check warns if the unit's students are likely double-booked (best-effort).

- **UC-32 — Allocate rooms** (EO)
  - *Pre:* session is `draft`; rooms exist.
  - *Flow:* pick room(s) → enter allocated capacity per room → save.
  - *Post:* RoomAllocations exist; sum matches `expected_candidates`.

- **UC-33 — Run allocation** (EO)
  - *Pre:* exam period is active; sessions are `scheduled`; rooms allocated.
  - *Flow:* open "Run allocation" → confirm → Celery task begins → progress is shown → on completion, the assignment grid is shown.
  - *Post:* `InvigilatorAssignment` rows exist; statuses default to `assigned`.
  - *Ex:* infeasible inputs (returns a structured error and leaves the database untouched).

- **UC-34 — Manual reassignment** (EO)
  - *Pre:* assignments exist.
  - *Flow:* pick session → pick invigilator → "Replace" → server picks the best replacement honouring all hard constraints → confirm.
  - *Post:* new assignment is `assigned`; old is `replaced`; audit row written.

### 2.5 Invigilator workflow

- **UC-40 — View personal schedule** (IN)
  - *Pre:* IN is logged in; has assignments.
  - *Flow:* open dashboard → see today's sessions and the next 7 days.
  - *Post:* none (read-only).

- **UC-41 — Check in** (IN)
  - *Pre:* IN has an `assigned` assignment for a session that has started (or starts within 30 minutes).
  - *Flow:* tap "Check in" → scan QR / enter PIN / tap button → record is written.
  - *Post:* `Attendance(check_in)` row exists; if late, the row has `late=true`.

- **UC-42 — Check out** (IN)
  - *Pre:* IN is checked in to a session.
  - *Flow:* tap "Check out" → record is written.
  - *Post:* `Attendance(check_out)` row exists.

- **UC-43 — Submit incident** (IN)
  - *Pre:* IN is checked in to a session (or has just been checked out).
  - *Flow:* open session → "Report incident" → pick category, write description, attach evidence → submit.
  - *Post:* `IncidentReport` row is `open`; EO is notified.

- **UC-44 — Declare availability** (IN)
  - *Pre:* exam period is announced.
  - *Flow:* open availability page → mark unavailable time ranges → save.
  - *Post:* availability rows exist; the allocator respects them.

### 2.6 Reporting and analytics

- **UC-50 — View dashboard** (SA, EO, HOD, DEA)
  - *Pre:* user is authenticated.
  - *Flow:* open dashboard → server fetches scoped overview → render cards and charts.
  - *Post:* none.

- **UC-51 — Generate a report** (SA, EO, HOD, DEA)
  - *Pre:* user is authenticated and has read access to the report's scope.
  - *Flow:* open Reports → pick a report and filters → choose format (PDF, Excel, CSV) → submit → download.
  - *Post:* file is delivered; for large reports, a job is enqueued and a notification is sent.

- **UC-52 — Drill into an incident** (SA, EO)
  - *Pre:* an incident exists.
  - *Flow:* open incident list → click row → see detail, evidence, audit history → mark investigating/resolved/closed.
  - *Post:* status is updated; audit row written.

### 2.7 System administration

- **UC-60 — Review audit log** (SA)
  - *Pre:* audit log exists.
  - *Flow:* open Audit → filter by actor, action, target, date → review.
  - *Post:* none.

- **UC-61 — Update system setting** (SA)
  - *Pre:* setting key is seed-defined.
  - *Flow:* open Settings → edit value → save.
  - *Post:* setting is in effect for subsequent reads; audit row written.

- **UC-62 — Unlock a locked account** (SA)
  - *Pre:* a user is locked.
  - *Flow:* open user → click "Unlock" → confirm.
  - *Post:* lockout is cleared; user can attempt login again.

---

## 3. Role-permission matrix

The matrix is the contract. Every cell that says ✓ means a user with that role has the permission **for the data within their scope** (see §4). The permissions themselves are stored in the `Permission` table and are referenced by `codename`.

| Codename | SA | EO | IN | HOD | DEA |
|----------|:--:|:--:|:--:|:---:|:---:|
| `accounts.user.view` | ✓ | ✓ (own profile) | ✓ (own) | ✓ (own) | ✓ (own) |
| `accounts.user.create` | ✓ |  |  |  |  |
| `accounts.user.update` | ✓ |  |  |  |  |
| `accounts.user.disable` | ✓ |  |  |  |  |
| `accounts.role.assign` | ✓ |  |  |  |  |
| `accounts.profile.update_own` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `academic.faculty.crud` | ✓ |  |  |  |  |
| `academic.department.crud` | ✓ |  |  |  |  |
| `academic.programme.crud` | ✓ | ✓ |  |  |  |
| `academic.course.crud` | ✓ | ✓ |  |  |  |
| `academic.unit.crud` | ✓ | ✓ |  |  |  |
| `people.student.crud` | ✓ | ✓ |  | ✓ (dept) | ✓ (faculty) |
| `people.student.import` | ✓ | ✓ |  |  |  |
| `people.invigilator.crud` | ✓ | ✓ |  | ✓ (dept) | ✓ (faculty) |
| `people.invigilator.import` | ✓ | ✓ |  |  |  |
| `people.availability.update_own` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `exam.period.crud` | ✓ | ✓ |  |  |  |
| `exam.session.crud` | ✓ | ✓ |  |  |  |
| `room.crud` | ✓ | ✓ |  |  |  |
| `room.allocate` | ✓ | ✓ |  |  |  |
| `allocator.run` | ✓ | ✓ |  |  |  |
| `allocator.reassign` | ✓ | ✓ |  |  |  |
| `attendance.checkin_own` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `attendance.view` | ✓ | ✓ (all) | ✓ (own) | ✓ (dept) | ✓ (faculty) |
| `incident.create` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `incident.view` | ✓ | ✓ (all) | ✓ (own) | ✓ (dept) | ✓ (faculty) |
| `incident.update_status` | ✓ | ✓ |  |  |  |
| `notification.view_own` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `notification.send` | ✓ | ✓ |  |  |  |
| `report.view` | ✓ | ✓ (all) | ✓ (own) | ✓ (dept) | ✓ (faculty) |
| `report.export` | ✓ | ✓ |  | ✓ | ✓ |
| `analytics.view` | ✓ | ✓ (all) | ✓ (own) | ✓ (dept) | ✓ (faculty) |
| `audit.view` | ✓ |  |  |  |  |
| `settings.read` | ✓ | ✓ |  |  |  |
| `settings.update` | ✓ |  |  |  |  |

### 3.1 How the matrix maps to data scope

- ✓ (own) — only the user's own records.
- ✓ (dept) — records linked to the user's department.
- ✓ (faculty) — records linked to any department in the user's faculty.
- ✓ (all) — all records in the system.

Scope is enforced by a **scoped queryset layer** in the API, not by the role check alone. Role checks answer "may this user touch this kind of entity?"; the scope layer answers "which rows?". This split keeps the permission table small and stable.

---

## 4. Scoped querysets

The data scope is implemented by a `ScopedQuerySetMixin` on the API viewset. The mixin reads the user's primary role and applies a filter:

| Role | Faculty filter | Department filter | Personal filter |
|------|----------------|-------------------|-----------------|
| SA | — | — | — |
| EO | — | — | — |
| IN | — | — | `invigilator_id = self.request.user.invigilator.id` |
| HOD | `faculty_id = …` | `department_id = …` | — |
| DEA | `faculty_id = …` | — | — |

For the IN role, "own" includes assignments where `invigilator_id` matches the user's invigilator row. The mixin is overridden in viewsets that need a different rule (e.g. `IncidentReport` is scoped by reporter or by the session's department).

---

## 5. Use-case-to-requirements traceability

A sampling (the full matrix is in the GitHub project):

| Use case | Functional requirements |
|----------|--------------------------|
| UC-01 Log in | FR-AUTH-01, FR-AUTH-02, FR-AUTH-09, FR-AUTH-10 |
| UC-03 Reset password | FR-AUTH-04, FR-AUTH-05, FR-AUTH-10 |
| UC-10 Create user | FR-USR-01, FR-USR-02, FR-AUTH-06, FR-AUD-01 |
| UC-24 Bulk import invigilators | FR-PER-02, FR-PER-04 |
| UC-33 Run allocation | FR-ALC-01, FR-ALC-03, FR-ALC-04, FR-ALC-05, FR-ALC-06, FR-ALC-07, FR-ALC-08 |
| UC-41 Check in | FR-ATT-01, FR-ATT-02, FR-ATT-03, FR-ATT-04 |
| UC-43 Submit incident | FR-INC-01, FR-INC-02 |
| UC-50 View dashboard | FR-ANL-01, FR-ANL-02, FR-ANL-03 |
| UC-51 Generate report | FR-RPT-01, FR-RPT-02, FR-RPT-03 |
| UC-60 Review audit log | FR-AUD-01, FR-AUD-02, FR-AUD-03 |
