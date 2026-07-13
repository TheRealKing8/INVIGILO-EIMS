"""Tests for admin-only user-management actions.

Covers the two elevated actions on :class:`UserViewSet`:

* ``POST /api/v1/users/{id}/reset-password/`` — sets a new password
  on behalf of the user. Gated by ``accounts.user.reset_password``
  (SYSTEM_ADMINISTRATOR only). Revokes all refresh tokens so the
  user must sign in again.
* ``POST /api/v1/users/{id}/set-roles/`` — replaces the user's role
  set. Gated by ``accounts.role.assign`` (SYSTEM_ADMINISTRATOR only).

The class-level ``accounts.user.create`` permission still works for
``list`` / ``create`` / ``update`` / ``destroy`` / ``unlock`` — this
phase introduces a method-level split, not a class-level one.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import RefreshToken, Role, UserRole


pytestmark = pytest.mark.django_db

User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def admin_role() -> Role:
    role, _ = Role.objects.update_or_create(
        code="SYSTEM_ADMINISTRATOR",
        defaults={"name": "System Administrator", "is_active": True},
    )
    return role


@pytest.fixture
def officer_role() -> Role:
    role, _ = Role.objects.update_or_create(
        code="EXAMINATION_OFFICER",
        defaults={"name": "Examination Officer", "is_active": True},
    )
    return role


@pytest.fixture
def admin_user(admin_role: Role) -> User:
    user = User.objects.create_user(
        email="admin@x.com",
        full_name="Admin",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=admin_role)
    return user


@pytest.fixture
def officer_user(officer_role: Role) -> User:
    user = User.objects.create_user(
        email="eo@x.com",
        full_name="Eo",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=officer_role)
    return user


@pytest.fixture
def target_user() -> User:
    """A regular invigilator that admins can target."""
    role, _ = Role.objects.update_or_create(
        code="INVIGILATOR",
        defaults={"name": "Invigilator", "is_active": True},
    )
    user = User.objects.create_user(
        email="alice@x.com",
        full_name="Alice",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=role)
    return user


def _auth_as(client: APIClient, user: User) -> None:
    """Force-authenticate a client for permission tests."""
    client.force_authenticate(user=user)


# ---------------------------------------------------------------------------
# reset_password
# ---------------------------------------------------------------------------
def test_admin_can_reset_user_password(
    client: APIClient, admin_user: User, target_user: User
) -> None:
    """SA POSTs ``reset-password``; the new password sticks and the
    user's refresh tokens are revoked."""
    # Issue the user a refresh token so we can assert revocation.
    from apps.accounts.services import auth as auth_service

    auth_service.issue_token_pair(target_user, request=None, response=None)
    assert RefreshToken.objects.filter(user=target_user, revoked_at__isnull=True).count() == 1

    _auth_as(client, admin_user)
    response = client.post(
        reverse("users:users-reset-password", kwargs={"pk": target_user.id}),
        {
            "new_password": "BrandNewPassw0rd!2026",
            "confirm_password": "BrandNewPassw0rd!2026",
        },
        format="json",
    )
    assert response.status_code == 204
    # Reload the user from the DB and check the new password.
    target_user.refresh_from_db()
    assert target_user.check_password("BrandNewPassw0rd!2026") is True
    # Old password no longer works.
    assert target_user.check_password("S3cur3Passw0rd!") is False
    # All refresh tokens revoked.
    assert (
        RefreshToken.objects.filter(user=target_user, revoked_at__isnull=True).count() == 0
    )


def test_officer_cannot_reset_password(
    client: APIClient, officer_user: User, target_user: User
) -> None:
    """EO does not hold ``accounts.user.reset_password`` — 403."""
    _auth_as(client, officer_user)
    response = client.post(
        reverse("users:users-reset-password", kwargs={"pk": target_user.id}),
        {
            "new_password": "BrandNewPassw0rd!2026",
            "confirm_password": "BrandNewPassw0rd!2026",
        },
        format="json",
    )
    assert response.status_code == 403
    # The user's password is unchanged.
    target_user.refresh_from_db()
    assert target_user.check_password("S3cur3Passw0rd!") is True


def test_reset_password_rejects_mismatched_confirm(
    client: APIClient, admin_user: User, target_user: User
) -> None:
    """Mismatched new/confirm → 400 from the serializer, no write."""
    _auth_as(client, admin_user)
    response = client.post(
        reverse("users:users-reset-password", kwargs={"pk": target_user.id}),
        {
            "new_password": "BrandNewPassw0rd!2026",
            "confirm_password": "DIFFERENTPassword!2026",
        },
        format="json",
    )
    assert response.status_code == 400
    target_user.refresh_from_db()
    assert target_user.check_password("S3cur3Passw0rd!") is True


# ---------------------------------------------------------------------------
# set_roles
# ---------------------------------------------------------------------------
def test_admin_can_set_user_roles(
    client: APIClient, admin_user: User, target_user: User
) -> None:
    """SA POSTs ``set-roles``; the response shows the new primary role."""
    _auth_as(client, admin_user)
    # Sanity: target starts as INVIGILATOR.
    assert target_user.has_role("INVIGILATOR")

    response = client.post(
        reverse("users:users-set-roles", kwargs={"pk": target_user.id}),
        {"roles": ["EXAMINATION_OFFICER"]},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    codes = [r["code"] for r in body["roles"]]
    assert codes == ["EXAMINATION_OFFICER"]
    # Reload and re-check the live relationship.
    target_user.refresh_from_db()
    assert target_user.has_role("EXAMINATION_OFFICER")
    assert not target_user.has_role("INVIGILATOR")


def test_officer_cannot_set_roles(
    client: APIClient, officer_user: User, target_user: User
) -> None:
    """EO does not hold ``accounts.role.assign`` — 403."""
    _auth_as(client, officer_user)
    response = client.post(
        reverse("users:users-set-roles", kwargs={"pk": target_user.id}),
        {"roles": ["EXAMINATION_OFFICER"]},
        format="json",
    )
    assert response.status_code == 403
    # The user's role set is unchanged.
    target_user.refresh_from_db()
    assert target_user.has_role("INVIGILATOR")
    assert not target_user.has_role("EXAMINATION_OFFICER")


def test_set_roles_rejects_unknown_code(
    client: APIClient, admin_user: User, target_user: User
) -> None:
    """Unknown role codes raise a 400 from the serializer."""
    _auth_as(client, admin_user)
    response = client.post(
        reverse("users:users-set-roles", kwargs={"pk": target_user.id}),
        {"roles": ["DOES_NOT_EXIST"]},
        format="json",
    )
    assert response.status_code == 400


def test_set_roles_revokes_user_refresh_tokens(
    client: APIClient, admin_user: User, target_user: User
) -> None:
    """Changing a user's roles must revoke their active refresh tokens.

    The JWT's ``permissions`` claim is baked at login time. A role
    change after login leaves a 0–15 minute stale window where the
    access token's permissions claim is wrong; revoking the refresh
    token means the next rotation fails immediately and the user
    has to re-auth to pick up the new role's permissions.
    """
    from apps.accounts.services import auth as auth_service

    auth_service.issue_token_pair(target_user, request=None, response=None)
    assert (
        RefreshToken.objects.filter(user=target_user, revoked_at__isnull=True).count() == 1
    )

    _auth_as(client, admin_user)
    response = client.post(
        reverse("users:users-set-roles", kwargs={"pk": target_user.id}),
        {"roles": ["INVIGILATOR", "EXAMINATION_OFFICER"]},
        format="json",
    )
    assert response.status_code == 200
    # All refresh tokens revoked.
    assert (
        RefreshToken.objects.filter(user=target_user, revoked_at__isnull=True).count() == 0
    )
