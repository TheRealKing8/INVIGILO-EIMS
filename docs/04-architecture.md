# INVIGILO — System Architecture

> Companion to `01-srs.md`, `02-requirements.md`, and `05-erd.md`. This document describes the *how*: the components, their responsibilities, the contracts between them, and the deployment topology.

---

## 1. Goals and constraints

The architecture must satisfy the non-functional requirements in `02-requirements.md`. The constraints that most influence the design are:

- **Stateless application tier** (NFR-SC-01) — any number of backend instances behind a load balancer.
- **Postgres 16** as the single source of truth.
- **Async work** (allocation, email, report generation) must be off the request path (NFR-RE-04).
- **Predictable deploys** in a university IT environment (often air-gapped, limited internet, conservative change windows).
- **Observability** must be possible without paid SaaS: structured logs, request IDs, simple health endpoints.

---

## 2. High-level architecture

```
                     ┌──────────────────────────────────────────────────────┐
                     │                     Browser (Next.js)                │
                     │  Server Components + Client Components + shadcn/ui   │
                     └──────────────────────┬───────────────────────────────┘
                                            │ HTTPS / JSON
                                            │ (JWT bearer in Authorization header)
                                            ▼
                              ┌──────────────────────────────┐
                              │      Nginx (TLS, gzip,       │
                              │      rate limit, static)     │
                              └──────────────┬───────────────┘
                                             │
                                ┌────────────┴────────────┐
                                ▼                         ▼
                  ┌────────────────────────┐  ┌────────────────────────┐
                  │   Django + DRF (gunicorn)│  │  Next.js (Node, node)  │
                  │   REST API + OpenAPI     │  │  Server-side rendering │
                  └──────┬─────────────┬─────┘  └────────────────────────┘
                         │             │
            sync reads/  │             │  async tasks (Celery)
              writes     ▼             ▼
                  ┌────────────┐   ┌────────────────────────────┐
                  │ PostgreSQL │   │ Redis (broker + cache)     │
                  │   16       │   └──────────┬─────────────────┘
                  └────────────┘              │
                                             ▼
                              ┌──────────────────────────────┐
                              │ Celery workers               │
                              │  - allocator                 │
                              │  - mailer                    │
                              │  - report_exporter           │
                              └──────────────────────────────┘
```

The browser talks to two origins: the **Django API** (for all data) and the **Next.js server** (for the rendered page shell + RSC data). The Next.js server then calls the Django API internally; clients never see the Django URL.

---

## 3. Component view

### 3.1 Django backend (`backend/`)

The backend is a single Django project (`invigilo`) composed of apps. Each app owns a bounded domain; cross-app imports are limited to the `invigilo` project module.

| App | Responsibility |
|-----|----------------|
| `accounts` | Custom `User`, role/permission RBAC, JWT issuance, profile, email verification, password reset. |
| `academic` | Faculty, Department, Programme, Course, Unit. |
| `people` | Student, Invigilator, availability. |
| `exam_periods` | ExamPeriod, ExamSession, scheduling constraints. |
| `rooms` | ExamRoom, RoomAllocation. |
| `allocator` | Smart allocation engine (services + Celery task + management command). |
| `attendance` | Attendance records, PIN, QR. |
| `incidents` | IncidentReport + evidence uploads. |
| `notifications` | In-app + email notifications. |
| `reports` | Report definitions + Celery exporters (PDF/Excel/CSV). |
| `analytics` | Aggregated read-only endpoints for the dashboard. |
| `audit` | Append-only audit log. |
| `core` | Project-level concerns: settings, base models, scoped queryset mixin, exception handler, OpenAPI hooks. |

### 3.2 Next.js frontend (`frontend/`)

App Router with route groups. Server Components for read paths, Client Components for interactivity.

```
frontend/
└── src/
    ├── app/                      # routes
    │   ├── (auth)/               # login, forgot, reset
    │   ├── (dashboard)/          # authenticated routes
    │   │   ├── dashboard/
    │   │   ├── academic/         # faculties, departments, programmes, courses, units
    │   │   ├── people/           # students, invigilators
    │   │   ├── exam-periods/
    │   │   ├── rooms/
    │   │   ├── allocator/        # run + reassign
    │   │   ├── attendance/
    │   │   ├── incidents/
    │   │   ├── reports/
    │   │   ├── analytics/
    │   │   └── settings/
    │   └── api/                  # BFF route handlers (thin) for cases where
    │                             # RSC cannot call Django directly
    ├── components/
    │   ├── ui/                   # shadcn primitives
    │   ├── data-table/           # generic sortable/filterable table
    │   ├── charts/               # Recharts wrappers
    │   └── forms/                # RHF + Zod form components
    ├── lib/
    │   ├── api/                  # typed API client (openapi-typescript)
    │   ├── auth/                 # token storage, refresh interceptor
    │   ├── rbac/                 # permission gates (client-side hints only)
    │   └── utils/
    ├── server/                   # server-only helpers (cookies, RSC fetch)
    ├── styles/
    └── types/
```

### 3.3 Database (`database/`)

Versioned SQL migrations live inside each Django app. The `database/` directory holds:

- `init.sql` — extensions and roles (idempotent).
- `seed/` — seed scripts for development (idempotent).
- `backups/` — operational notes for backup and restore (no actual dumps in version control).

### 3.4 Docker and deployment (`docker/`)

- `docker/Dockerfile.backend` — multi-stage, slim Python 3.13.
- `docker/Dockerfile.frontend` — multi-stage, Next.js standalone output.
- `docker/nginx.conf` — reverse proxy + TLS + rate limit.
- `docker-compose.yml` (project root) — local stack: postgres, redis, backend, celery, beat, frontend, nginx.

---

## 4. Process view

### 4.1 Request lifecycle (read)

1. Browser requests a page.
2. Next.js Server Component runs.
3. RSC authenticates the request by reading the access token from the HttpOnly cookie.
4. RSC calls Django (`GET /api/<resource>/`) with a server-side fetch using a service token derived from the user.
5. Django returns JSON; RSC streams the rendered HTML.
6. Client Components hydrate; subsequent reads use React Query (server-state cache) talking to Django via the browser.

### 4.2 Request lifecycle (write)

1. Client submits a form.
2. React Hook Form + Zod validate client-side.
3. POST to Django with bearer token.
4. Django permission class + scoped queryset + serializer validate.
5. Service layer performs the work inside `transaction.atomic()`.
6. Audit row is written.
7. Response is 2xx with the created/updated resource; the client invalidates React Query.

### 4.3 Allocation lifecycle

1. EO clicks "Run allocation".
2. POST `/api/allocations/` with `exam_period_id`.
3. View enqueues a Celery task and returns `202 Accepted` with the task id.
4. Frontend polls `GET /api/allocations/<id>/` (or opens an SSE stream) for status.
5. Celery worker:
   1. Locks the ExamPeriod (`SELECT ... FOR UPDATE`).
   2. Loads sessions, rooms, invigilators, availability.
   3. Runs the allocator (see §5).
   4. Writes assignments transactionally.
   6. Emits a notification to each affected invigilator.
   7. Marks the run `succeeded` or `failed` with diagnostics.
6. Frontend updates the assignment grid.

---

## 5. The Smart Allocation Engine

The allocator is a **constraint-satisfaction problem** solved greedily with a workload-balancing heuristic. It is implemented as a pure service (`allocator/services/allocate.py`) and is independently testable.

### 5.1 Algorithm

```
Inputs:
  - exam_period
  - sessions[]  (each: id, start, end, expected_candidates, room_set[])
  - invigilators[]  (each: id, dept, max_daily, max_weekly, availability[])
  - rule_capacity(expected_candidates) -> required_invigilators

Pre-conditions (enforced by the caller):
  - sessions are ordered by start time
  - room_set sums to expected_candidates
  - no session overlaps a same-student conflict (best-effort check at scheduling time)

Steps:
  1. For each session s in order:
       a. n := rule_capacity(s.expected_candidates)
       b. eligible := invigilators not assigned to an overlapping session
                      and not unavailable in [s.start, s.end]
                      and below their daily/weekly max
       c. Sort eligible by:
            - same department as the unit (preferred)
            - fewest total assignments in the period so far (workload balance)
            - fewest lead roles assigned so far
            - stable tie-breaker on id (for determinism)
       d. Pick the first n. The first is the lead.
       e. Write n InvigilatorAssignment rows.
  2. If at any step |eligible| < n, the run is marked infeasible for that session.
     The engine keeps going to report the maximum set of feasible assignments and
     returns a structured error with the list of under-staffed sessions.

Post-conditions:
  - C1, C2, C3, C4 hold for every emitted assignment
  - O1, O2, O3 are best-effort
  - The output is deterministic given the same inputs
```

The algorithm is **O(S × I log I)** where S = sessions and I = invigilators; for 1,000 sessions and 200 invigilators this is well under a second on commodity hardware. The 60-second NFR (NFR-PE-03) covers more complex reports and the database write of 1,000 × 4 = 4,000 rows.

### 5.2 Idempotence

`allocate(period)` deletes all `InvigilatorAssignment` rows where `assigned_by IS NULL` (i.e. system-assigned) for that period, then re-creates them. The deletion + recreation is wrapped in a single transaction. Manual assignments (rows where `assigned_by` is set) are preserved.

This makes the engine re-runnable: the EO can change inputs and click "Re-run"; the grid is rebuilt to the optimal state for the new inputs.

### 5.3 Why not OR-tools / CP-SAT?

For 1,000 sessions and 200 invigilators, a greedy algorithm with a good ordering is sufficient, deterministic, and trivially explainable to non-technical stakeholders ("we always prefer someone from the same department, and within that, whoever has done the fewest sessions"). A constraint solver becomes attractive only above ~10,000 sessions or when soft constraints dominate. The engine's input layer is decoupled from the algorithm so a solver backend can be swapped in later.

---

## 6. Cross-cutting concerns

### 6.1 Authentication flow

- Login → server issues access (15 min) + refresh (7 d) tokens.
- Access token is stored in an HttpOnly cookie for RSC, and in memory (closure variable) for the browser's Axios interceptor.
- Refresh token is stored in an HttpOnly cookie scoped to `/api/auth/`.
- The Axios interceptor calls `POST /api/auth/refresh` on 401, swaps the access token, and retries the original request once.

### 6.2 Authorisation

Two layers, in order:

1. **Permission class** (`IsAuthenticated`, `HasPermission(<codename>)`) — answers "may this user touch this kind of entity?".
2. **Scoped queryset mixin** — answers "which rows?".

The second layer is essential: a HOD with `people.invigilator.crud` may only edit invigilators in their department. The mixin reads the user's primary role and applies the appropriate filter at `get_queryset()`.

### 6.3 Audit logging

A single `audit.services.record()` function is called from every place that mutates a security- or business-critical entity. The function runs *inside* the same transaction as the mutation, so an audit row exists if and only if the mutation was committed. There is no public API to update or delete an audit row; an admin with database access can disable the constraint, but the API forbids it.

### 6.4 Email

- Outbound email goes through Celery (`mailer` queue).
- Each delivery writes a `Notification` row.
- The same `Notification` row is updated with `delivered_at` once SMTP returns 2xx.
- Failures are retried up to 3 times with exponential backoff (5 min, 30 min, 3 h).

### 6.5 File uploads

- Evidence and avatars go to a `MEDIA_ROOT` volume (local) or an S3 bucket (production).
- The URL is stored on the model; the file is served by Nginx with a 1-year cache header.
- Uploads are validated for size and MIME type on both client and server.

### 6.6 Time and time zones

- `USE_TZ = True` everywhere. All timestamps in DB are UTC.
- The user's `time_zone` field (IANA name) is used to render timestamps in the UI.
- Sessions are stored as `DateTimeField`; the "date" of a session is the local date at the institution.

### 6.7 Observability

- Structured JSON logging with a request id middleware.
- `/api/health/` (DB + Redis) and `/api/ready/` (migrations applied) for k8s/liveness checks.
- Optional Sentry integration via `SENTRY_DSN`.

---

## 7. Security model

- All traffic terminates TLS at Nginx.
- `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Content-Security-Policy` are set on every response.
- Cookies: `HttpOnly; Secure; SameSite=Lax`.
- The Django `SECRET_KEY` is loaded from the environment and rotated via the secret manager.
- Database credentials are not used by the application after initialisation; a separate read-only user is used for any future reporting view.
- Rate limits (NFR-SE-06) are enforced at Nginx for the API and at DRF for sensitive endpoints (login).

---

## 8. Deployment topology

A single-host Docker Compose stack is the v1 default. The same images run in a multi-host production deployment behind a load balancer.

### 8.1 Local (docker-compose)

```
┌─────────────────────────────────────────────────────────────┐
│                          host                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ nginx :443  │  │ frontend :3000│  │ backend :8000      │  │
│  │             │──▶│              │──▶│ gunicorn          │  │
│  │             │  │              │  │                    │  │
│  │             │  │              │  │ celery worker      │  │
│  │             │  │              │  │ celery beat        │  │
│  └─────────────┘  └──────────────┘  └────────┬───────────┘  │
│                                              │              │
│                                ┌─────────────┴───────────┐  │
│                                │                         │  │
│                          ┌─────▼──────┐         ┌────────▼─┐│
│                          │ postgres   │         │  redis   ││
│                          └────────────┘         └──────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Production

Same images; nginx terminates TLS; backend and Celery scale horizontally behind systemd / Kubernetes; Postgres is the institution's managed instance; Redis is the institution's managed instance. Media is mounted from an S3-compatible bucket.

### 8.3 CI/CD (GitHub Actions)

- `lint` — ruff, black, eslint, prettier.
- `typecheck` — mypy (backend), tsc (frontend).
- `test` — pytest with coverage; vitest with coverage.
- `build` — build both images; tag with the commit SHA.
- `deploy` — manual approval gate; pushes to a private registry; triggers the deploy hook on the institution's environment.

---

## 9. Trade-offs and alternatives considered

| Decision | Alternative considered | Why we chose this |
|----------|------------------------|-------------------|
| **Django + DRF** | FastAPI | Django's admin, ORM, migrations, and auth ecosystem beat FastAPI for a CRUD-heavy enterprise app; the cost is lower raw throughput, which we don't need. |
| **PostgreSQL** | MySQL | JSONB (`AuditLog.metadata`, `SystemSetting.value`), partial indexes, generated columns. |
| **Celery + Redis** | RQ, dramatiq | Celery's maturity, monitoring, and beat scheduler are unmatched; the overhead is acceptable. |
| **shadcn/ui** | Material UI, Chakra | Tailwind-native, server-component-friendly, copy-paste ownership of the code (no runtime dependency to upgrade). |
| **React Query** | SWR, server components only | RSC handles the read path; React Query handles client-side mutation, optimistic updates, and refetch on focus. |
| **Greedy allocator** | OR-tools CP-SAT | Sufficient for v1; swap path is open. |
| **Single-binary Next.js** | Serverless | University IT rarely runs serverless; a long-lived node process is more diagnosable. |

---

## 10. Open questions

These are tracked in the GitHub project; each has an owner and a target milestone.

- **OQ-01** — Do we expose a public API for partner institutions? (v1.1, owner: TBA)
- **OQ-02** — Do we support SSO (SAML / OIDC) with the institution's IdP? (v1.1, owner: TBA)
- **OQ-03** — Where do evidence files live long-term? (S3 vs on-prem) — depends on institution's data policy.
