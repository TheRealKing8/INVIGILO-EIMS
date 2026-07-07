# INVIGILO — Documentation

This directory holds the full design record for INVIGILO. Every file in the codebase can be traced back to a requirement here.

## Read in this order

1. **[01-srs.md](01-srs.md)** — Software Requirements Specification, Part 1 (introduction, scope, definitions).
2. **[02-requirements.md](02-requirements.md)** — Functional and non-functional requirements, acceptance criteria.
3. **[03-use-cases.md](03-use-cases.md)** — Actor profiles, use-case catalogue, role-permission matrix, scoped querysets.
4. **[04-architecture.md](04-architecture.md)** — System architecture, components, deployment, the smart allocation engine.
5. **[05-erd.md](05-erd.md)** — Entity-relationship model, indexes, migration plan.
6. **[06-folder-structure.md](06-folder-structure.md)** — Source tree, module map, conventions.

## How requirements map to code

| You are… | Read first | Then read |
|----------|------------|-----------|
| A new backend engineer | 01 → 04 §3–5 → 05 → 06 §2 | 02 (functional requirements) |
| A new frontend engineer | 01 → 04 §3.2 → 06 §3 | 02 (functional requirements) |
| A reviewer signing off a milestone | 02 (acceptance criteria) | 03 (role matrix) |
| A DevOps engineer | 04 §7–8 → 06 §5 | 04 §6 (observability) |
| A security reviewer | 02 §2.2 (security NFRs) | 04 §7 | 03 §3 (RBAC) |
| A product owner | 01 → 02 → 03 | 04 (high-level) |

## Phase roadmap

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 1 | SRS, use cases, architecture, ERD, folder structure | **Complete (this set)** |
| 2 | Django scaffold, DRF, JWT, Postgres, Docker, env | Next |
| 3 | Accounts, roles, RBAC, academic hierarchy | Pending |
| 4 | Exam periods, sessions, rooms | Pending |
| 5 | Smart allocation engine | Pending |
| 6 | Attendance, incidents, notifications | Pending |
| 7 | Reports, analytics dashboard | Pending |
| 8 | Audit logs, system settings, polish | Pending |

## Change control

The docs are versioned with the code. When a requirement changes:

1. Open a PR that updates the relevant file in this directory.
2. Reference the requirement ID (e.g. `FR-ALC-03`) in the commit body.
3. Add a one-line entry to the changelog section in the modified file.

The current docs version is **1.0.0-draft**.
