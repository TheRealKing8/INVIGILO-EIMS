"""Static seed data for the RBAC system.

The role/permission matrix is the contract documented in
``docs/03-use-cases.md`` §3. Changing it requires:

1. Editing this file.
2. Editing the matrix in ``03-use-cases.md``.
3. Adding a data migration to re-seed if the change is non-additive.
"""
from __future__ import annotations

from typing import Final


# ----------------------------------------------------------------------------
# Roles
# ----------------------------------------------------------------------------
ROLES: Final[tuple[dict, ...]] = (
    {
        "code": "SYSTEM_ADMINISTRATOR",
        "name": "System Administrator",
        "description": "Operates the platform, manages users, roles, and settings.",
    },
    {
        "code": "EXAMINATION_OFFICER",
        "name": "Examination Officer",
        "description": "Builds timetables, runs the allocator, oversees operations.",
    },
    {
        "code": "INVIGILATOR",
        "name": "Invigilator",
        "description": "Accepts assignments, checks in/out, reports incidents.",
    },
    {
        "code": "HEAD_OF_DEPARTMENT",
        "name": "Head of Department",
        "description": "Approves invigilators, reviews departmental reports.",
    },
    {
        "code": "FACULTY_DEAN",
        "name": "Faculty Dean",
        "description": "Faculty-level oversight and reports.",
    },
)


# ----------------------------------------------------------------------------
# Permission codenames (the full set, across every app)
# ----------------------------------------------------------------------------
PERMISSIONS: Final[tuple[dict, ...]] = (
    # accounts
    {"codename": "accounts.user.view", "name": "View users"},
    {"codename": "accounts.user.create", "name": "Create users"},
    {"codename": "accounts.user.update", "name": "Update users"},
    {"codename": "accounts.user.disable", "name": "Disable users"},
    {"codename": "accounts.role.assign", "name": "Assign roles"},
    {"codename": "accounts.profile.update_own", "name": "Update own profile"},
    # academic
    {"codename": "academic.faculty.crud", "name": "Manage faculties"},
    {"codename": "academic.department.crud", "name": "Manage departments"},
    {"codename": "academic.programme.crud", "name": "Manage programmes"},
    {"codename": "academic.course.crud", "name": "Manage courses"},
    {"codename": "academic.unit.crud", "name": "Manage units"},
    # people
    {"codename": "people.student.crud", "name": "Manage students"},
    {"codename": "people.student.import", "name": "Bulk import students"},
    {"codename": "people.invigilator.crud", "name": "Manage invigilators"},
    {"codename": "people.invigilator.import", "name": "Bulk import invigilators"},
    {"codename": "people.availability.update_own", "name": "Update own availability"},
    # exam periods
    {"codename": "exam.period.crud", "name": "Manage exam periods"},
    {"codename": "exam.session.crud", "name": "Manage exam sessions"},
    # rooms
    {"codename": "room.crud", "name": "Manage rooms"},
    {"codename": "room.allocate", "name": "Allocate rooms"},
    # allocator
    {"codename": "allocator.run", "name": "Run allocation"},
    {"codename": "allocator.reassign", "name": "Manually reassign"},
    # attendance
    {"codename": "attendance.checkin_own", "name": "Check in (own)"},
    {"codename": "attendance.view", "name": "View attendance"},
    # incidents
    {"codename": "incident.create", "name": "Submit incident"},
    {"codename": "incident.view", "name": "View incidents"},
    {"codename": "incident.update_status", "name": "Update incident status"},
    # notifications
    {"codename": "notification.view_own", "name": "View own notifications"},
    {"codename": "notification.send", "name": "Send notifications"},
    # reports
    {"codename": "report.view", "name": "View reports"},
    {"codename": "report.export", "name": "Export reports"},
    # analytics
    {"codename": "analytics.view", "name": "View analytics"},
    # audit
    {"codename": "audit.view", "name": "View audit log"},
    # settings
    {"codename": "settings.read", "name": "View system settings"},
    {"codename": "settings.update", "name": "Update system settings"},
)


# ----------------------------------------------------------------------------
# Role -> permissions
# ----------------------------------------------------------------------------
# Order: (role_code, [permission_codenames])
ROLE_PERMISSIONS: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    (
        "SYSTEM_ADMINISTRATOR",
        tuple(p["codename"] for p in PERMISSIONS),
    ),
    (
        "EXAMINATION_OFFICER",
        (
            "accounts.profile.update_own",
            "academic.programme.crud",
            "academic.course.crud",
            "academic.unit.crud",
            "people.student.crud",
            "people.student.import",
            "people.invigilator.crud",
            "people.invigilator.import",
            "people.availability.update_own",
            "exam.period.crud",
            "exam.session.crud",
            "room.crud",
            "room.allocate",
            "allocator.run",
            "allocator.reassign",
            "attendance.checkin_own",
            "attendance.view",
            "incident.create",
            "incident.view",
            "incident.update_status",
            "notification.view_own",
            "notification.send",
            "report.view",
            "report.export",
            "analytics.view",
            "settings.read",
        ),
    ),
    (
        "INVIGILATOR",
        (
            "accounts.profile.update_own",
            "people.availability.update_own",
            "attendance.checkin_own",
            "attendance.view",
            "incident.create",
            "incident.view",
            "notification.view_own",
            "report.view",
            "analytics.view",
        ),
    ),
    (
        "HEAD_OF_DEPARTMENT",
        (
            "accounts.profile.update_own",
            "people.availability.update_own",
            "people.student.crud",
            "people.invigilator.crud",
            "attendance.checkin_own",
            "attendance.view",
            "incident.create",
            "incident.view",
            "notification.view_own",
            "report.view",
            "report.export",
            "analytics.view",
        ),
    ),
    (
        "FACULTY_DEAN",
        (
            "accounts.profile.update_own",
            "people.availability.update_own",
            "people.student.crud",
            "people.invigilator.crud",
            "attendance.checkin_own",
            "attendance.view",
            "incident.create",
            "incident.view",
            "notification.view_own",
            "report.view",
            "report.export",
            "analytics.view",
        ),
    ),
)


__all__ = ["PERMISSIONS", "ROLES", "ROLE_PERMISSIONS"]
