# INVIGILO — Folder Structure and Module Map

> Companion to `04-architecture.md` §3. This is the source tree that Phases 2+ will create. Every directory has a single responsibility. Every file has a one-line purpose.

---

## 1. Top-level layout

```
Examination-Invigilation-Management-System/
├── backend/                # Django + DRF + Celery
├── frontend/               # Next.js 15 (App Router) + TypeScript + Tailwind
├── database/               # SQL init, seeds, ops notes
├── docker/                 # Dockerfiles, nginx config
├── docs/                   # this documentation set
├── .github/                # workflows, CODEOWNERS
├── docker-compose.yml      # local stack
├── .env.example            # committed env template
├── .gitignore
├── LICENSE
└── README.md
```

---

## 2. Backend (`backend/`)

```
backend/
├── pyproject.toml              # build + tool config (ruff, black, mypy, pytest)
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── manage.py
├── conftest.py                 # pytest-django configuration
├── pytest.ini
├── .env.example
├── .gitignore
│
├── invigilo/                   # Django project package
│   ├── __init__.py
│   ├── asgi.py
│   ├── wsgi.py
│   ├── celery.py               # Celery app instance
│   ├── urls.py                 # root URL conf
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py             # shared settings
│   │   ├── dev.py
│   │   ├── test.py
│   │   └── prod.py
│   └── middleware/
│       ├── __init__.py
│       ├── request_id.py       # X-Request-ID + logging context
│       └── audit_context.py    # binds current user/actor to audit calls
│
├── apps/
│   ├── __init__.py
│   │
│   ├── core/                   # shared primitives
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── models.py           # BaseModel, TimestampedModel, SoftDeleteModel
│   │   ├── permissions.py      # HasPermission, IsRole
│   │   ├── scopes.py           # ScopedQuerySetMixin
│   │   ├── exceptions.py       # domain exception types
│   │   ├── pagination.py       # default PageNumberPagination
│   │   ├── exceptions_handler.py
│   │   ├── filters.py          # common filter sets
│   │   └── management/
│   │       └── commands/
│   │           └── seed_demo.py
│   │
│   ├── accounts/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── admin.py
│   │   ├── models.py           # User, Role, Permission, refresh token, etc.
│   │   ├── managers.py
│   │   ├── serializers.py
│   │   ├── views.py            # AuthViewSet, UserViewSet
│   │   ├── urls.py
│   │   ├── filters.py
│   │   ├── permissions.py      # module-specific perm classes
│   │   ├── services/
│   │   │   ├── auth.py         # login, refresh, logout, verify, reset
│   │   │   └── users.py
│   │   ├── tasks.py            # email verification, password reset
│   │   ├── migrations/
│   │   └── tests/
│   │       ├── test_models.py
│   │       ├── test_auth_api.py
│   │       └── test_permissions.py
│   │
│   ├── academic/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── admin.py
│   │   ├── models.py           # Faculty, Department, Programme, Course, Unit
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── filters.py
│   │   ├── services/
│   │   │   └── import_csv.py   # bulk import (used by tests too)
│   │   ├── migrations/
│   │   └── tests/
│   │
│   ├── people/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── admin.py
│   │   ├── models.py           # Student, Invigilator, Availability
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── filters.py
│   │   ├── services/
│   │   │   ├── import_csv.py
│   │   │   └── availability.py
│   │   ├── migrations/
│   │   └── tests/
│   │
│   ├── exam_periods/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── admin.py
│   │   ├── models.py           # ExamPeriod, ExamSession
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── filters.py
│   │   ├── services/
│   │   │   ├── scheduling.py   # conflict checks
│   │   │   └── lifecycle.py    # status transitions
│   │   ├── migrations/
│   │   └── tests/
│   │
│   ├── rooms/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── admin.py
│   │   ├── models.py           # ExamRoom, RoomAllocation
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── filters.py
│   │   ├── services/
│   │   │   └── allocation.py   # capacity rules, conflict checks
│   │   ├── migrations/
│   │   └── tests/
│   │
│   ├── allocator/              # the smart allocation engine
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── admin.py
│   │   ├── models.py           # InvigilatorAssignment, AllocRun
│   │   ├── serializers.py
│   │   ├── views.py            # POST /api/allocations/, GET status
│   │   ├── urls.py
│   │   ├── services/
│   │   │   ├── allocate.py     # the pure algorithm
│   │   │   ├── capacity.py     # rule_capacity(expected)
│   │   │   └── reorder.py      # scoring (department, workload, lead)
│   │   ├── tasks.py            # Celery task that runs allocate()
│   │   ├── management/
│   │   │   └── commands/
│   │   │       └── allocate.py # synchronous CLI entry point
│   │   ├── migrations/
│   │   └── tests/
│   │       ├── test_capacity.py
│   │       ├── test_allocate.py
│   │       ├── test_constraints.py
│   │       └── test_idempotence.py
│   │
│   ├── attendance/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── admin.py
│   │   ├── models.py           # Attendance, Pin
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── services/
│   │   │   ├── check_in.py
│   │   │   ├── pin.py
│   │   │   └── qr.py
│   │   ├── tasks.py
│   │   ├── migrations/
│   │   └── tests/
│   │
│   ├── incidents/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── admin.py
│   │   ├── models.py           # IncidentReport, Evidence
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── filters.py
│   │   ├── services/
│   │   │   ├── submit.py
│   │   │   └── status.py
│   │   ├── migrations/
│   │   └── tests/
│   │
│   ├── notifications/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── admin.py
│   │   ├── models.py           # Notification
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── services/
│   │   │   ├── dispatch.py
│   │   │   └── email.py
│   │   ├── tasks.py            # Celery mailer
│   │   ├── migrations/
│   │   └── tests/
│   │
│   ├── reports/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── admin.py
│   │   ├── models.py           # ReportDefinition, ReportExport
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── services/
│   │   │   ├── registry.py     # built-in report definitions
│   │   │   ├── renderers/
│   │   │   │   ├── pdf.py      # ReportLab
│   │   │   │   ├── excel.py    # OpenPyXL
│   │   │   │   └── csv.py
│   │   │   └── runner.py
│   │   ├── tasks.py
│   │   ├── migrations/
│   │   └── tests/
│   │
│   ├── analytics/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── views.py            # GET /api/analytics/overview
│   │   ├── urls.py
│   │   ├── services/
│   │   │   └── overview.py     # aggregate counts, scoped by role
│   │   └── tests/
│   │
│   ├── audit/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── admin.py            # read-only
│   │   ├── models.py           # AuditLog
│   │   ├── services.py         # record()
│   │   ├── views.py            # search
│   │   ├── urls.py
│   │   ├── filters.py
│   │   ├── migrations/
│   │   └── tests/
│   │
│   └── settings_app/           # system settings (named to avoid clash with django.conf.settings)
│       ├── __init__.py
│       ├── apps.py
│       ├── models.py           # SystemSetting
│       ├── serializers.py
│       ├── views.py
│       ├── urls.py
│       ├── services.py
│       ├── migrations/
│       └── tests/
│
└── scripts/
    ├── create_demo_data.py     # management script wrapper
    └── reset_db.sh
```

### 2.1 Backend conventions

- **One app per domain.** No cross-app imports of models. Cross-app relations go through explicit `apps.<x>.models.<Model>` references, never through string-based reverse lookups.
- **Service layer is the only place that mutates more than one model.** Views and tasks call services. Services raise domain exceptions; the exception handler in `core.exceptions_handler` maps them to HTTP responses.
- **Tests live next to the code they test**, in a `tests/` package, not a top-level `tests/` directory.
- **Migrations are committed and ordered by the framework.** We do not squash.

---

## 3. Frontend (`frontend/`)

```
frontend/
├── package.json
├── pnpm-lock.yaml             # pnpm is the package manager
├── next.config.mjs             # standalone output, security headers
├── tsconfig.json              # strict: true
├── tailwind.config.ts
├── postcss.config.mjs
├── components.json            # shadcn config
├── .env.example
├── .eslintrc.cjs
├── .prettierrc
├── vitest.config.ts
├── playwright.config.ts       # E2E (later milestone)
│
├── public/
│   ├── favicon.ico
│   └── logo.svg
│
├── src/
│   ├── middleware.ts          # auth gate for /(dashboard)
│   │
│   ├── app/
│   │   ├── layout.tsx          # root layout (theme, query, toaster)
│   │   ├── globals.css
│   │   ├── page.tsx            # redirect → /dashboard or /login
│   │   ├── (auth)/
│   │   │   ├── layout.tsx
│   │   │   ├── login/page.tsx
│   │   │   ├── forgot/page.tsx
│   │   │   ├── reset/page.tsx
│   │   │   └── verify/page.tsx
│   │   ├── (dashboard)/
│   │   │   ├── layout.tsx      # sidebar + topbar
│   │   │   ├── dashboard/page.tsx
│   │   │   ├── academic/
│   │   │   │   ├── faculties/page.tsx
│   │   │   │   ├── faculties/[id]/page.tsx
│   │   │   │   ├── departments/page.tsx
│   │   │   │   ├── departments/[id]/page.tsx
│   │   │   │   ├── programmes/page.tsx
│   │   │   │   ├── programmes/[id]/page.tsx
│   │   │   │   ├── courses/page.tsx
│   │   │   │   ├── courses/[id]/page.tsx
│   │   │   │   ├── units/page.tsx
│   │   │   │   └── units/[id]/page.tsx
│   │   │   ├── people/
│   │   │   │   ├── students/page.tsx
│   │   │   │   ├── students/[id]/page.tsx
│   │   │   │   ├── invigilators/page.tsx
│   │   │   │   └── invigilators/[id]/page.tsx
│   │   │   ├── exam-periods/
│   │   │   │   ├── page.tsx
│   │   │   │   └── [id]/page.tsx
│   │   │   ├── rooms/
│   │   │   │   ├── page.tsx
│   │   │   │   └── [id]/page.tsx
│   │   │   ├── allocator/
│   │   │   │   ├── page.tsx
│   │   │   │   └── runs/[id]/page.tsx
│   │   │   ├── attendance/
│   │   │   │   ├── page.tsx                    # my attendance
│   │   │   │   └── sessions/[id]/page.tsx      # EO view
│   │   │   ├── incidents/
│   │   │   │   ├── page.tsx
│   │   │   │   ├── new/page.tsx
│   │   │   │   └── [id]/page.tsx
│   │   │   ├── reports/
│   │   │   │   ├── page.tsx
│   │   │   │   ├── [code]/page.tsx
│   │   │   │   └── exports/[id]/page.tsx
│   │   │   ├── analytics/page.tsx
│   │   │   ├── notifications/page.tsx
│   │   │   ├── settings/
│   │   │   │   ├── page.tsx
│   │   │   │   ├── users/page.tsx
│   │   │   │   ├── roles/page.tsx
│   │   │   │   ├── audit/page.tsx
│   │   │   │   └── system/page.tsx
│   │   │   └── profile/page.tsx
│   │   └── api/                                # BFF route handlers (thin)
│   │       ├── revalidate/route.ts
│   │       └── health/route.ts
│   │
│   ├── components/
│   │   ├── ui/                                # shadcn primitives, generated
│   │   ├── data-table/
│   │   │   ├── data-table.tsx
│   │   │   ├── data-table-toolbar.tsx
│   │   │   ├── data-table-pagination.tsx
│   │   │   └── data-table-skeleton.tsx
│   │   ├── charts/
│   │   │   ├── bar.tsx
│   │   │   ├── line.tsx
│   │   │   └── pie.tsx
│   │   ├── forms/
│   │   │   ├── form.tsx                        # RHF wrapper
│   │   │   ├── text-field.tsx
│   │   │   ├── select-field.tsx
│   │   │   └── submit-button.tsx
│   │   ├── nav/
│   │   │   ├── sidebar.tsx
│   │   │   ├── topbar.tsx
│   │   │   ├── breadcrumbs.tsx
│   │   │   └── user-menu.tsx
│   │   ├── feedback/
│   │   │   ├── toaster.tsx
│   │   │   ├── confirm-dialog.tsx
│   │   │   ├── empty-state.tsx
│   │   │   └── error-state.tsx
│   │   └── theme/
│   │       ├── theme-provider.tsx
│   │       └── theme-toggle.tsx
│   │
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts                       # Axios instance
│   │   │   ├── auth.ts                         # token interceptor
│   │   │   └── endpoints.ts                    # typed endpoint helpers
│   │   ├── auth/
│   │   │   ├── session.ts                      # server-side session
│   │   │   └── guards.ts
│   │   ├── rbac/
│   │   │   ├── permissions.ts                  # codename list
│   │   │   ├── gate.tsx                        # <Gate code="...">
│   │   │   └── use-permission.ts
│   │   ├── query/
│   │   │   ├── query-client.ts
│   │   │   └── providers.tsx
│   │   ├── utils/
│   │   │   ├── cn.ts                           # classnames
│   │   │   ├── date.ts                         # tz-aware formatting
│   │   │   └── download.ts
│   │   └── validators/                         # zod schemas (mirror DRF)
│   │       ├── user.ts
│   │       ├── exam-session.ts
│   │       └── ...
│   │
│   ├── server/                                 # server-only helpers
│   │   ├── cookies.ts
│   │   ├── rsc-fetch.ts
│   │   └── auth.ts
│   │
│   ├── types/
│   │   ├── api.d.ts                            # generated from OpenAPI
│   │   └── domain.ts
│   │
│   └── styles/
│       └── globals.css
│
└── tests/
    ├── unit/                                   # vitest
    │   ├── rbac.test.ts
    │   └── validators.test.ts
    └── e2e/                                    # playwright (later)
```

### 3.1 Frontend conventions

- **App Router only.** No `pages/` directory.
- **Server Components by default.** A component is `"use client"` only when it needs state, effects, or browser APIs.
- **Data fetching on the server uses RSC**; the same data is re-fetched on the client with React Query after a mutation.
- **shadcn primitives live in `components/ui` and are committed to the repo** so we control the version exactly.
- **The BFF (`app/api/*`) is for thin passes** — e.g. a route that proxies a file download. The default path is RSC → Django.

---

## 4. Database (`database/`)

```
database/
├── init.sql                    # CREATE EXTENSION citext, pgcrypto; roles
├── seed/
│   ├── roles.sql               # seed the 5 roles
│   ├── permissions.sql         # seed the permission codenames
│   ├── role_permissions.sql    # seed the role-permission matrix
│   └── settings.sql            # seed system settings
├── migrations/                 # notes; the real migrations are in apps/
│   └── README.md
└── ops/
    ├── backup.sh
    ├── restore.sh
    └── README.md
```

The seed SQL is the canonical source for the role/permission matrix; the same data is loaded by a Django data migration so test runs and dev runs see the same state.

---

## 5. Docker (`docker/`)

```
docker/
├── Dockerfile.backend
├── Dockerfile.frontend
├── nginx/
│   ├── nginx.conf
│   ├── conf.d/
│   │   ├── api.conf            # upstream gunicorn
│   │   ├── web.conf            # upstream next
│   │   └── security-headers.conf
│   └── ssl/
│       └── README.md           # how to drop in certs
├── backend.entrypoint.sh       # wait-for-db, migrate, collectstatic
├── frontend.entrypoint.sh
├── celery.worker.entrypoint.sh
└── celery.beat.entrypoint.sh
```

The Dockerfiles are multi-stage: a builder stage installs dependencies, a runtime stage copies only the wheel/installed packages and the application code.

---

## 6. GitHub Actions (`.github/`)

```
.github/
├── CODEOWNERS
├── PULL_REQUEST_TEMPLATE.md
├── ISSUE_TEMPLATE/
│   ├── bug.md
│   └── feature.md
└── workflows/
    ├── backend-ci.yml          # ruff, black, mypy, pytest
    ├── frontend-ci.yml         # eslint, prettier, tsc, vitest
    ├── build.yml               # docker buildx
    ├── deploy.yml              # manual gate
    └── codeql.yml              # security analysis
```

Each CI job runs on push to `main` and on PRs. A status check on `main` requires the full backend + frontend suites to pass.

---

## 7. Environment variables (`.env.example`)

The committed template lists every variable, the format, an example, and which component consumes it.

```bash
# General
APP_ENV=dev
APP_NAME=invigilo
APP_URL=http://localhost:8080
TZ=UTC

# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=invigilo
POSTGRES_USER=invigilo
POSTGRES_PASSWORD=change-me

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# Backend
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CORS_ALLOWED_ORIGINS=http://localhost:3000

# JWT
JWT_ACCESS_LIFETIME_MINUTES=15
JWT_REFRESH_LIFETIME_DAYS=7

# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=mailhog
EMAIL_PORT=1025
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=0
EMAIL_FROM=noreply.invigilo@gmail.com

# Frontend
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Secrets in production are not in `.env`; they are injected by the secret manager (NFR-SE-09).

---

## 8. README and landing

`README.md` (project root) is the single page the user lands on when they open the repo. It contains:

- One-line description.
- Badges (CI, license, version).
- "What is INVIGILO?" with a screenshot placeholder.
- "Quick start" (docker-compose up).
- "Documentation" linking to `docs/`.
- "Project status" (which phase is done).
- "Contributing" and "License".

`docs/README.md` is the documentation index — a one-line description and a link to every document in the set.
