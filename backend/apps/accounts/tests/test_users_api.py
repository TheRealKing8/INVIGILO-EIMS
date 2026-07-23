"""Tests for the broader CRUD surface of :class:`UserViewSet`.

The two SA-only elevated actions (``reset_password`` + ``set_roles``)
live in :mod:`test_user_admin`. This file covers the six remaining
endpoints that share the class-level ``accounts.user.create``
codename — ``list`` / ``retrieve`` / ``create`` / ``partial_update`` /
``destroy`` / ``unlock`` — none of which had a direct test before.

Why this file exists
--------------------
The UserViewSet is the only admin surface that doesn't use
``ModelViewSet`` + ``django-filter`` + ``PageNumberPagination`` — it's
a hand-rolled ``ViewSet`` that returns a flat array. The flat
``list`` shape is intentionally documented as "fine for a few hundred
users" (``api.ts:1346-1350``). Before any of those endpoints get
re-shaped, the contract needs test coverage so the existing
behaviour can't quietly regress.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
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
def invigilator_role() -> Role:
    role, _ = Role.objects.update_or_create(
        code="INVIGILATOR",
        defaults={"name": "Invigilator", "is_active": True},
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
def invigilator_user(invigilator_role: Role) -> User:
    """An INVIGILATOR does NOT hold ``accounts.user.create`` — used to
    assert the CRUD surface is SA-only."""
    user = User.objects.create_user(
        email="inv@x.com",
        full_name="Inv",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=invigilator_role)
    return user


def _auth_as(client: APIClient, user: User) -> None:
    client.force_authenticate(user=user)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
def test_list_requires_authentication(client: APIClient) -> None:
    """Unauthenticated GET /users/ → 401 (IsAuthenticated is part of
    the class-level permission chain)."""
    response = client.get(reverse("users:users-list"))
    assert response.status_code == 401


def test_list_forbidden_for_non_sa(client: APIClient, invigilator_user: User) -> None:
    """An invigilator does not hold ``accounts.user.create`` → 403."""
    _auth_as(client, invigilator_user)
    response = client.get(reverse("users:users-list"))
    assert response.status_code == 403


def test_list_returns_active_users_only(
    client: APIClient, admin_user: User
) -> None:
    """Soft-deleted users are excluded by ``User.objects`` (the
    SoftDeleteUserManager). The disabled user must NOT appear in the
    list, but the admin caller must."""
    User.objects.create_user(
        email="ghost@x.com",
        full_name="Ghost",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
        is_active=False,
    )
    _auth_as(client, admin_user)
    response = client.get(reverse("users:users-list"))
    assert response.status_code == 200
    emails = [u["email"] for u in response.json()]
    assert "admin@x.com" in emails
    assert "ghost@x.com" not in emails


def test_list_is_sorted_by_email(client: APIClient, admin_user: User) -> None:
    """The endpoint pins ``order_by("email")`` (a flat array, not
    paginated). Assert the order so a future "switch to pagination"
    refactor doesn't quietly change it."""
    for email in ("zeta@x.com", "alpha@x.com", "mike@x.com"):
        User.objects.create_user(
            email=email,
            full_name=email.split("@")[0].title(),
            password="S3cur3Passw0rd!",
            is_email_verified=True,
        )
    _auth_as(client, admin_user)
    response = client.get(reverse("users:users-list"))
    assert response.status_code == 200
    emails = [u["email"] for u in response.json()]
    assert emails == sorted(emails)


# ---------------------------------------------------------------------------
# retrieve
# ---------------------------------------------------------------------------
def test_retrieve_returns_target_user(client: APIClient, admin_user: User) -> None:
    target = User.objects.create_user(
        email="bob@x.com",
        full_name="Bob",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    _auth_as(client, admin_user)
    response = client.get(reverse("users:users-retrieve", kwargs={"pk": target.id}))
    assert response.status_code == 200
    assert response.json()["email"] == "bob@x.com"


def test_retrieve_returns_404_for_unknown_id(client: APIClient, admin_user: User) -> None:
    """A well-formed UUID that doesn't match any row → 404, not 500."""
    import uuid

    _auth_as(client, admin_user)
    response = client.get(
        reverse("users:users-retrieve", kwargs={"pk": uuid.uuid4()})
    )
    assert response.status_code == 404


def test_retrieve_404_for_soft_deleted_user(
    client: APIClient, admin_user: User
) -> None:
    """The detail endpoint uses the default ``User.objects`` manager,
    so a soft-deleted target is invisible (404) — the admin must not
    be able to PATCH / DELETE a row that doesn't exist in their
    default view."""
    target = User.objects.create_user(
        email="doomed@x.com",
        full_name="Doomed",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
        is_active=False,
    )
    _auth_as(client, admin_user)
    response = client.get(reverse("users:users-retrieve", kwargs={"pk": target.id}))
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------
def test_create_user_minimal_payload(client: APIClient, admin_user: User) -> None:
    """``POST /users/`` with just email + full_name + password works.
    The response is the new user's full ``UserSerializer`` shape."""
    _auth_as(client, admin_user)
    response = client.post(
        reverse("users:users-list"),
        {
            "email": "new@x.com",
            "full_name": "New User",
            "password": "BrandNewPassw0rd!2026",
        },
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@x.com"
    # The password is NOT echoed back in the response.
    assert "password" not in body
    # The user is real and can sign in.
    new_user = User.objects.get(email="new@x.com")
    assert new_user.check_password("BrandNewPassw0rd!2026") is True


def test_create_user_with_roles(client: APIClient, admin_user: User) -> None:
    """The serializer accepts a ``roles`` list — every code must
    resolve to a real Role row, or the serializer 422s."""
    _auth_as(client, admin_user)
    response = client.post(
        reverse("users:users-list"),
        {
            "email": "role@x.com",
            "full_name": "Role User",
            "password": "BrandNewPassw0rd!2026",
            "roles": ["INVIGILATOR"],
        },
        format="json",
    )
    assert response.status_code == 201
    new_user = User.objects.get(email="role@x.com")
    assert new_user.has_role("INVIGILATOR") is True


def test_create_user_rejects_unknown_role(
    client: APIClient, admin_user: User
) -> None:
    """Unknown role code → 400 from the serializer, no row written."""
    _auth_as(client, admin_user)
    response = client.post(
        reverse("users:users-list"),
        {
            "email": "badrole@x.com",
            "full_name": "Bad Role",
            "password": "BrandNewPassw0rd!2026",
            "roles": ["NOT_A_REAL_ROLE"],
        },
        format="json",
    )
    assert response.status_code == 400
    assert User.objects.filter(email="badrole@x.com").exists() is False


def test_create_user_rejects_duplicate_email(
    client: APIClient, admin_user: User
) -> None:
    """Duplicate email → 400 (the email column is unique)."""
    User.objects.create_user(
        email="dup@x.com",
        full_name="Dup",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    _auth_as(client, admin_user)
    response = client.post(
        reverse("users:users-list"),
        {
            "email": "dup@x.com",
            "full_name": "Another Dup",
            "password": "BrandNewPassw0rd!2026",
        },
        format="json",
    )
    assert response.status_code == 400


def test_create_user_rejects_weak_password(
    client: APIClient, admin_user: User
) -> None:
    """``UserCreateSerializer`` runs the same complexity validators
    the rest of the auth flow uses — ``"short"`` is 5 chars, single
    class. The 422 keeps the no-row-written invariant."""
    _auth_as(client, admin_user)
    response = client.post(
        reverse("users:users-list"),
        {
            "email": "weak@x.com",
            "full_name": "Weak",
            "password": "short",
        },
        format="json",
    )
    assert response.status_code == 422
    assert User.objects.filter(email="weak@x.com").exists() is False


# ---------------------------------------------------------------------------
# partial_update
# ---------------------------------------------------------------------------
def test_partial_update_phone_and_timezone(
    client: APIClient, admin_user: User
) -> None:
    """PATCH only touches the fields in the payload — the rest of the
    user row is left alone (especially email, which the
    ``UserUpdateSerializer`` doesn't include)."""
    target = User.objects.create_user(
        email="ed@x.com",
        full_name="Ed",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    _auth_as(client, admin_user)
    response = client.patch(
        reverse("users:users-retrieve", kwargs={"pk": target.id}),
        {"phone": "+254700000000", "time_zone": "Africa/Nairobi"},
        format="json",
    )
    assert response.status_code == 200
    target.refresh_from_db()
    assert target.phone == "+254700000000"
    assert target.time_zone == "Africa/Nairobi"
    # Untouched.
    assert target.email == "ed@x.com"
    assert target.full_name == "Ed"


def test_partial_update_rejects_unknown_target(
    client: APIClient, admin_user: User
) -> None:
    """Unknown UUID → 404, not 500."""
    import uuid

    _auth_as(client, admin_user)
    response = client.patch(
        reverse("users:users-retrieve", kwargs={"pk": uuid.uuid4()}),
        {"phone": "+254700000000"},
        format="json",
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# destroy
# ---------------------------------------------------------------------------
def test_destroy_soft_deletes_user_and_revokes_tokens(
    client: APIClient, admin_user: User
) -> None:
    """``DELETE /users/{id}/`` calls ``soft_delete()`` (is_active=False)
    AND revokes every active refresh token. The user row stays in
    the table so audit log entries can still resolve to a name."""
    from apps.accounts.services import auth as auth_service

    target = User.objects.create_user(
        email="bye@x.com",
        full_name="Bye",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    auth_service.issue_token_pair(target, request=None, response=None)
    assert (
        RefreshToken.objects.filter(user=target, revoked_at__isnull=True).count() == 1
    )

    _auth_as(client, admin_user)
    response = client.delete(reverse("users:users-retrieve", kwargs={"pk": target.id}))
    assert response.status_code == 204

    target.refresh_from_db()
    assert target.is_active is False
    # Row is still in the DB (``User.all_objects``), but invisible to
    # the default manager.
    assert User.all_objects.filter(pk=target.id).exists() is True
    assert User.objects.filter(pk=target.id).exists() is False
    # All refresh tokens revoked.
    assert (
        RefreshToken.objects.filter(user=target, revoked_at__isnull=True).count() == 0
    )


def test_destroy_returns_404_for_unknown_target(
    client: APIClient, admin_user: User
) -> None:
    import uuid

    _auth_as(client, admin_user)
    response = client.delete(
        reverse("users:users-retrieve", kwargs={"pk": uuid.uuid4()})
    )
    assert response.status_code == 404


def test_destroy_404_for_already_disabled_user(
    client: APIClient, admin_user: User
) -> None:
    """The default ``User.objects`` manager is used — an
    already-disabled user is invisible, so the second DELETE is 404,
    not 204. (Idempotency is the caller's job.)"""
    target = User.objects.create_user(
        email="gone@x.com",
        full_name="Gone",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
        is_active=False,
    )
    _auth_as(client, admin_user)
    response = client.delete(reverse("users:users-retrieve", kwargs={"pk": target.id}))
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# unlock
# ---------------------------------------------------------------------------
def test_unlock_clears_failed_login_and_lockout(
    client: APIClient, admin_user: User
) -> None:
    """A locked user (``failed_login_count >= 5`` + ``locked_until``
    in the future) is brought back to a clean state. ``unlock`` uses
    ``User.all_objects`` so already-disabled users are still unlockable
    — useful for the recovery flow."""
    target = User.objects.create_user(
        email="locked@x.com",
        full_name="Locked",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    target.failed_login_count = 5
    target.locked_until = timezone.now() + timedelta(minutes=15)
    target.save(update_fields=("failed_login_count", "locked_until", "updated_at"))

    _auth_as(client, admin_user)
    response = client.post(reverse("users:users-unlock", kwargs={"pk": target.id}))
    assert response.status_code == 204

    target.refresh_from_db()
    assert target.failed_login_count == 0
    assert target.locked_until is None


def test_unlock_works_on_disabled_user(
    client: APIClient, admin_user: User
) -> None:
    """``unlock`` is the only CRUD action that uses
    ``User.all_objects`` — an admin can clear a disabled user's
    failed-login counter so that re-enabling them later doesn't leave
    them one typo away from re-locking."""
    target = User.all_objects.create_user(
        email="disabled-locked@x.com",
        full_name="Disabled Locked",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
        is_active=False,
    )
    target.failed_login_count = 5
    target.locked_until = timezone.now() + timedelta(minutes=15)
    target.save(update_fields=("failed_login_count", "locked_until", "updated_at"))

    _auth_as(client, admin_user)
    response = client.post(reverse("users:users-unlock", kwargs={"pk": target.id}))
    assert response.status_code == 204
    target.refresh_from_db()
    assert target.failed_login_count == 0


def test_unlock_returns_404_for_unknown_target(
    client: APIClient, admin_user: User
) -> None:
    import uuid

    _auth_as(client, admin_user)
    response = client.post(
        reverse("users:users-unlock", kwargs={"pk": uuid.uuid4()})
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Permission gating — the whole CRUD surface is SA-only
# ---------------------------------------------------------------------------
def test_invigilator_cannot_create_user(
    client: APIClient, invigilator_user: User
) -> None:
    _auth_as(client, invigilator_user)
    response = client.post(
        reverse("users:users-list"),
        {
            "email": "sneak@x.com",
            "full_name": "Sneak",
            "password": "BrandNewPassw0rd!2026",
        },
        format="json",
    )
    assert response.status_code == 403
    assert User.objects.filter(email="sneak@x.com").exists() is False


def test_invigilator_cannot_update_user(
    client: APIClient, invigilator_user: User
) -> None:
    target = User.objects.create_user(
        email="victim@x.com",
        full_name="Victim",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    _auth_as(client, invigilator_user)
    response = client.patch(
        reverse("users:users-retrieve", kwargs={"pk": target.id}),
        {"phone": "+254711111111"},
        format="json",
    )
    assert response.status_code == 403
    target.refresh_from_db()
    assert target.phone == ""


def test_invigilator_cannot_destroy_user(
    client: APIClient, invigilator_user: User
) -> None:
    target = User.objects.create_user(
        email="target@x.com",
        full_name="Target",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    _auth_as(client, invigilator_user)
    response = client.delete(reverse("users:users-retrieve", kwargs={"pk": target.id}))
    assert response.status_code == 403
    target.refresh_from_db()
    assert target.is_active is True
