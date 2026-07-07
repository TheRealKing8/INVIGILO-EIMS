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

    role = Role.objects.create(code="EXAMINATION_OFFICER", name="EO")
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

    role = Role.objects.create(code="INVIGILATOR", name="IN")
    perm = Permission.objects.create(codename="people.invigilator.crud", name="X")
    RolePermission.objects.create(role=role, permission=perm)
    user = User.objects.create_user(email="u@x.com", full_name="U")
    UserRole.objects.create(user=user, role=role)
    request = _fake_request(user)
    p = HasPermission()
    assert p.has_permission(request, _stub_view(required=("people.invigilator.crud",))) is True
    assert p.has_permission(request, _stub_view(required=("people.invigilator.view",))) is False
