"""Tests for the permission classes in :mod:`apps.core.permissions`."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

from apps.core.permissions import HasPermission, IsRole, IsSuperAdmin


pytestmark = pytest.mark.django_db

User = get_user_model()


def _fake_request(user):  # type: ignore[no-untyped-def]
    factory = APIRequestFactory()
    request = factory.get("/")
    request.user = user
    return request


def _stub_view(required: tuple[str, ...] = ()) -> SimpleNamespace:
    return SimpleNamespace(required_permissions=required)


def test_is_superadmin_rejects_anonymous() -> None:
    request = _fake_request(SimpleNamespace(is_authenticated=False))
    assert IsSuperAdmin().has_permission(request, _stub_view()) is False


def test_is_superadmin_rejects_regular_user() -> None:
    user = User.objects.create_user(email="u@x.com", full_name="U")
    request = _fake_request(user)
    assert IsSuperAdmin().has_permission(request, _stub_view()) is False


def test_is_superadmin_accepts_staff() -> None:
    user = User.objects.create_user(email="s@x.com", full_name="S", is_staff=True)
    request = _fake_request(user)
    assert IsSuperAdmin().has_permission(request, _stub_view()) is True


def test_is_role_accepts_holding_role() -> None:
    from apps.accounts.models import Role, UserRole

    role, _ = Role.objects.update_or_create(
        code="EXAMINATION_OFFICER", defaults={"name": "EO", "is_active": True}
    )
    user = User.objects.create_user(email="e@x.com", full_name="E")
    UserRole.objects.create(user=user, role=role)
    request = _fake_request(user)
    perm = IsRole.with_roles("EXAMINATION_OFFICER", "INVIGILATOR")
    assert perm().has_permission(request, _stub_view()) is True


def test_is_role_rejects_without_role() -> None:
    user = User.objects.create_user(email="e@x.com", full_name="E")
    request = _fake_request(user)
    perm = IsRole.with_roles("EXAMINATION_OFFICER")
    assert perm().has_permission(request, _stub_view()) is False


def test_has_permission_via_view_attribute() -> None:
    from apps.accounts.models import Permission, Role, RolePermission, UserRole

    role, _ = Role.objects.update_or_create(
        code="INVIGILATOR", defaults={"name": "IN", "is_active": True}
    )
    perm, _ = Permission.objects.update_or_create(
        codename="people.invigilator.crud", defaults={"name": "X"}
    )
    RolePermission.objects.update_or_create(role=role, permission=perm)
    user = User.objects.create_user(email="u@x.com", full_name="U")
    UserRole.objects.update_or_create(user=user, role=role)
    request = _fake_request(user)
    p = HasPermission()
    assert p.has_permission(request, _stub_view(required=("people.invigilator.crud",))) is True
    assert p.has_permission(request, _stub_view(required=("people.invigilator.view",))) is False


# ---------------------------------------------------------------------------
# Module 1 — extended RBAC: STUDENT, SECURITY_OFFICER, GUEST
# ---------------------------------------------------------------------------
def _attach_role(user, code: str, name: str) -> None:
    """Helper — upsert a role by code and attach it to the user."""
    from apps.accounts.models import Role, UserRole

    role, _ = Role.objects.update_or_create(
        code=code, defaults={"name": name, "is_active": True}
    )
    UserRole.objects.update_or_create(user=user, role=role)


def test_student_has_only_narrow_permission_set() -> None:
    """STUDENT can check in to their own sessions but cannot manage users."""
    user = User.objects.create_user(email="s@x.com", full_name="S")
    _attach_role(user, "STUDENT", "Student")
    assert user.has_permission("attendance.checkin_own") is True
    assert user.has_permission("timetable.view_own") is True
    # Crucially, no admin codename leaks in.
    assert user.has_permission("settings.update") is False
    assert user.has_permission("accounts.user.create") is False
    assert user.has_permission("allocator.run") is False
    # The primary role code resolves to STUDENT.
    assert user.primary_role_code == "STUDENT"


def test_security_officer_can_update_incident_status_but_not_users() -> None:
    """SECURITY_OFFICER can triage incidents but cannot create users."""
    user = User.objects.create_user(email="sec@x.com", full_name="Sec")
    _attach_role(user, "SECURITY_OFFICER", "Security Officer")
    assert user.has_permission("incident.update_status") is True
    assert user.has_permission("attendance.checkin_any") is True
    # Not an admin.
    assert user.has_permission("settings.update") is False
    assert user.has_permission("accounts.user.create") is False
    assert user.has_permission("allocator.run") is False
    assert user.primary_role_code == "SECURITY_OFFICER"


def test_guest_has_minimal_read_only_access() -> None:
    """GUEST sees only the public timetable and own notifications."""
    user = User.objects.create_user(email="g@x.com", full_name="G")
    _attach_role(user, "GUEST", "Guest")
    assert user.has_permission("timetable.public.view") is True
    assert user.has_permission("notification.view_own") is True
    # No write access of any kind.
    assert user.has_permission("incident.create") is False
    assert user.has_permission("attendance.checkin_own") is False
    assert user.has_permission("report.view") is False
    assert user.primary_role_code == "GUEST"


def test_primary_role_picks_highest_precedence_among_mixed_roles() -> None:
    """A user with both INVIGILATOR and GUEST gets INVIGILATOR.

    Confirms the precedence update in :py:attr:`User.primary_role_code`
    — operational roles (INVIGILATOR) outrank low-trust roles (GUEST).
    """
    user = User.objects.create_user(email="mix@x.com", full_name="Mix")
    _attach_role(user, "GUEST", "Guest")
    _attach_role(user, "INVIGILATOR", "Invigilator")
    assert user.primary_role_code == "INVIGILATOR"


def test_superuser_bypasses_everything() -> None:
    """A superuser passes every HasPermission check regardless of roles."""
    user = User.objects.create_user(
        email="su@x.com", full_name="SU", is_superuser=True, is_staff=True
    )
    p = HasPermission()
    request = _fake_request(user)
    # Even with no roles attached, has_permission returns True.
    assert user.has_permission("allocator.run") is True
    assert user.has_permission("settings.update") is True
    assert p.has_permission(request, _stub_view(required=("allocator.run",))) is True
