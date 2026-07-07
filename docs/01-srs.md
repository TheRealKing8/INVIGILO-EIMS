# INVIGILO — Software Requirements Specification
## Part 1 of 2 — Introduction

> **Document set**
> - `01-srs.md` — this file. Introduction, scope, definitions, references, overview.
> - `02-requirements.md` — Functional and non-functional requirements, acceptance criteria.
> - `03-use-cases.md` — Actor profiles, use-case catalogue, role-permission matrix.
> - `04-architecture.md` — System architecture, components, deployment.
> - `05-erd.md` — Entity-relationship model.
> - `06-folder-structure.md` — Module map and source tree.
>
> Conforms in spirit to **IEEE 29148:2018** (requirements engineering) and **ISO/IEC 25010:2011** (quality model). This is not a tutorial artefact — it is the contract Phase 2 onward will be built against.

---

## 1. Purpose

This Software Requirements Specification (SRS) describes INVIGILO, a web-based Examination Invigilation Management System for universities and colleges. The SRS is the single source of truth for what the system does, the constraints under which it operates, and the qualities it must possess to be deemed acceptable by the institution.

The intended audiences are:

- **Product owner and stakeholders** — to confirm scope and prioritise work.
- **Backend, frontend, database, and DevOps engineers** — to drive implementation.
- **QA engineers** — to derive test plans and acceptance tests.
- **Security and audit reviewers** — to validate compliance posture.
- **Operations staff (university IT, examination office)** — to plan deployment, support, and training.

Successive phases of the project (Phases 2+) will be validated against this document. Any deviation from the requirements here is a change request, not a development liberty.

---

## 2. Scope

### 2.1 Product name
**INVIGILO** — Smart Examination Invigilation Management System.

### 2.2 What the product does

INVIGILO automates the full lifecycle of an institutional examination period:

1. **Setup** — faculties, departments, programmes, courses, units, students, invigilators, rooms.
2. **Scheduling** — exam periods, sessions, room allocation.
3. **Allocation** — an intelligent engine that assigns invigilators to sessions, respecting availability, workload, and capacity rules.
4. **Operation** — invigilator check-in / check-out, attendance, incident reporting, notifications.
5. **Closure** — reports, exports, analytics, audit trail.

### 2.3 What the product does NOT do

The following are **explicitly out of scope** for the current release. Recording them prevents scope drift.

- Online exam content authoring, delivery, or proctoring video analysis.
- Student registration, fee management, or transcript generation (the system *imports* student and unit data; it does not own them).
- Lecture timetable management (it consumes unit/semester data but does not build weekly class timetables).
- Mobile-native applications (the web app must be responsive on mobile browsers; no iOS/Android client).
- Payment processing.
- Live video surveillance integration.
- Multi-tenant SaaS isolation (the design supports a single institution per deployment; multi-tenant is a future release).

### 2.4 User classes

Five primary user classes are recognised. Detailed profiles are in `03-use-cases.md`.

| ID | Role | Primary responsibility |
|----|------|------------------------|
| SA  | System Administrator | Operate the platform, manage users, settings, audit |
| EO  | Examination Officer | Build timetables, run allocation, oversee operations |
| IN  | Invigilator | Accept assignments, check in/out, report incidents |
| HOD | Head of Department | Approve invigilators, view departmental reports |
| DEA | Faculty Dean | Faculty-level oversight and reports |

### 2.5 Operating environment

- **Deployment target:** Linux server (Ubuntu 22.04 LTS or later), Docker 24+, Docker Compose v2.
- **Web clients:** latest two stable versions of Chrome, Edge, Firefox, Safari. Mobile Safari and Chrome on Android (responsive layout, not a native app).
- **Network:** the system operates inside the institution's network, exposed through a reverse proxy with TLS termination.
- **Time zone:** the institution's local time; all timestamps stored in UTC and rendered in the user's chosen time zone.
- **Accessibility target:** WCAG 2.1 Level AA.

---

## 3. Definitions, acronyms, abbreviations

| Term | Definition |
|------|------------|
| **Allocation engine** | The component that assigns invigilators to exam sessions. See `04-architecture.md` §5. |
| **API** | Application Programming Interface. In this document, the HTTP/JSON API exposed by the backend. |
| **Audit log** | Immutable, append-only record of security- and business-relevant actions. |
| **Capacity rule** | The deterministic rule that maps room occupancy to the number of invigilators required (1–50→1, 51–100→2, 101–150→3, 151+→4). |
| **Celery** | Distributed task queue for Python/Django. Used for the allocation job. |
| **CRUD** | Create, Read, Update, Delete — the four basic persistent operations. |
| **DRF** | Django REST Framework. |
| **EO** | Examination Officer (user class). |
| **ExamPeriod** | A bounded window (e.g. "Semester 1 / 2026 — Final Examinations") within which ExamSessions are scheduled. |
| **ExamSession** | A specific sitting of a Unit's exam (date, start time, duration, venue). |
| **Faculty** | The top-level academic division (e.g. Faculty of Science). |
| **HOD** | Head of Department (user class). |
| **Invigilator** | A staff member assigned to supervise an exam. |
| **JWT** | JSON Web Token. Used for stateless API authentication. |
| **Permission** | An atomic capability (e.g. `invigilator.create`, `report.export`). |
| **RBAC** | Role-Based Access Control. Permissions are attached to Roles, which are attached to Users. |
| **Role** | A named set of Permissions, assigned to Users. |
| **Room** | A physical or virtual examination venue with a capacity. |
| **Unit** | A course component (a single examinable subject in a programme). |
| **Workload** | The total number of invigilator assignments held by a person over a window of time. |

---

## 4. References

| ID | Reference |
|----|-----------|
| R1 | IEEE Std 29148:2018 — Systems and software engineering — Life cycle processes — Requirements engineering. |
| R2 | ISO/IEC 25010:2011 — Systems and software engineering — Systems and software Quality Requirements and Evaluation (SQuaRE) — System and software quality models. |
| R3 | WCAG 2.1 — Web Content Accessibility Guidelines, Level AA. |
| R4 | OWASP Top 10 (2021) — application security baseline. |
| R5 | Django 5.x documentation — coding conventions and security guidance. |
| R6 | Next.js 15 App Router documentation — routing, server components, data fetching. |
| R7 | drf-spectacular — OpenAPI 3 schema generation for DRF. |
| R8 | SimpleJWT — JWT authentication for DRF. |

---

## 5. Document overview

The remainder of the documentation set is structured so each file answers one question:

- **What** is being built? → `02-requirements.md` (functional + non-functional requirements).
- **Who** uses it, and how? → `03-use-cases.md` (actor profiles, use cases, RBAC matrix).
- **How** is it built? → `04-architecture.md` (architecture, components, deployment) and `05-erd.md` (data model).
- **Where** does the code live? → `06-folder-structure.md` (module map).

A new contributor should read files in this order. A reviewer signing off on a milestone should be able to point to a specific requirement ID in `02-requirements.md` from any code change.

---

## 6. Change control

This document is versioned in Git. Changes require:

1. A change description in the commit body referencing the section affected.
2. A migration note in `docs/CHANGELOG.md` if any schema or API contract is affected.
3. Sign-off from the product owner for any change that alters scope, NFRs, or actor behaviour.

The current version is **1.0.0-draft**, corresponding to the start of Phase 2.
