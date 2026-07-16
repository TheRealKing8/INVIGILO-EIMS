"""Tests for the staff QR endpoints.

Two endpoints in this app mint staff QR tokens:

  * ``GET /api/v1/invigilators/profiles/me/qr.png/`` — the *caller's*
    own QR. Any authenticated user can hit it; the token is bound
    to ``request.user``. Used by the invigilator / EO / admin
    self-check-in flow on the day.
  * ``GET /api/v1/invigilators/profiles/{id}/qr.png/`` — an
    *operator* (SA/EO/HR with ``people.invigilator.crud``) fetches
    *another* invigilator's QR for verification. The token is still
    bound to the *target* user, so scanning checks THEM in.

Five tests, split between the two surfaces:

  1. ``me/qr.png`` returns a real PNG.
  2. ``me/qr.png`` rotates — two calls produce two distinct rows.
  3. ``{id}/qr.png`` mints a token bound to the *target*, not the
     *caller* (the security model — a screenshot checks THEM in).
  4. ``{id}/qr.png`` requires ``people.invigilator.crud``; a
     regular invigilator without that perm gets 403.
  5. ``{id}/qr.png`` returns 404 for a non-existent profile.
"""
from __future__ import annotations

import io

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.exams.qr_tokens import verify_qr_token
from apps.exams.student_registration import QrToken
from apps.invigilators.models import InvigilatorProfile

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def inv_user(db):  # type: ignore[no-untyped-def]
    """A second user with an InvigilatorProfile — the *target* of
    the operator view test. Distinct from ``verified_user`` so the
    token-binds-to-target assertion is meaningful."""
    role, _ = Role.objects.update_or_create(
        code="INVIGILATOR", defaults={"name": "Invigilator", "is_active": True}
    )
    user = User.objects.create_user(
        email="target@x.com", full_name="Target", password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=role)
    InvigilatorProfile.objects.update_or_create(user=user, defaults={})
    return user


@pytest.fixture
def manager_user(db):  # type: ignore[no-untyped-def]
    """A user with ``people.invigilator.crud`` — the *operator*
    who is allowed to fetch another invigilator's QR."""
    role, _ = Role.objects.update_or_create(
        code="MANAGER", defaults={"name": "Manager", "is_active": True}
    )
    perm, _ = Permission.objects.update_or_create(
        codename="people.invigilator.crud", defaults={"name": "Manage invigilators"}
    )
    RolePermission.objects.update_or_create(role=role, permission=perm)
    user = User.objects.create_user(
        email="manager@x.com", full_name="Manager", password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=role)
    return user


from django.contrib.auth import get_user_model  # noqa: E402

User = get_user_model()


# ---------------------------------------------------------------------------
# /me/qr.png — caller's own QR
# ---------------------------------------------------------------------------
def test_my_qr_returns_png(client: APIClient, verified_user) -> None:  # type: ignore[no-untyped-def]
    client.force_authenticate(verified_user)
    response = client.get("/api/v1/invigilators/profiles/me/qr.png/")
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"
    # And Pillow can open it.
    from PIL import Image

    img = Image.open(io.BytesIO(response.content))
    img.verify()
    assert img.size[0] > 0 and img.size[1] > 0


def test_my_qr_rotates_token(client: APIClient, verified_user) -> None:  # type: ignore[no-untyped-def]
    """Two calls produce two distinct QrToken rows."""
    client.force_authenticate(verified_user)
    QrToken.objects.filter(user=verified_user).delete()
    first = client.get("/api/v1/invigilators/profiles/me/qr.png/")
    second = client.get("/api/v1/invigilators/profiles/me/qr.png/")
    assert first.status_code == 200
    assert second.status_code == 200
    assert QrToken.objects.filter(user=verified_user, kind="staff").count() == 2


# ---------------------------------------------------------------------------
# /profiles/{id}/qr.png — operator view
# ---------------------------------------------------------------------------
def test_operator_qr_binds_to_target(
    client: APIClient, manager_user, inv_user
) -> None:  # type: ignore[no-untyped-def]
    """The token must be bound to the *target* invigilator's user,
    not the *caller*. If we bound it to the caller, an operator
    fetching the QR for an absent invigilator could walk in as
    themselves — which is a bigger hole than the one we are
    trying to plug."""
    target_profile = InvigilatorProfile.objects.get(user=inv_user)
    client.force_authenticate(manager_user)
    response = client.get(
        f"/api/v1/invigilators/profiles/{target_profile.id}/qr.png/"
    )
    assert response.status_code == 200, response.content
    assert response["Content-Type"] == "image/png"
    # Exactly one new staff token was minted, bound to the *target*.
    rows = QrToken.objects.filter(kind="staff")
    assert rows.count() == 1
    assert rows.first().user_id == inv_user.id


def test_operator_qr_requires_perm(
    client: APIClient, verified_user, inv_user
) -> None:  # type: ignore[no-untyped-def]
    """A regular user (no ``people.invigilator.crud``) gets 403.
    A non-admin trying to screenshot an invigilator's QR is the
    threat model this gate exists to stop."""
    target_profile = InvigilatorProfile.objects.get(user=inv_user)
    client.force_authenticate(verified_user)
    response = client.get(
        f"/api/v1/invigilators/profiles/{target_profile.id}/qr.png/"
    )
    assert response.status_code == 403
    # And no token was minted.
    assert QrToken.objects.filter(kind="staff").count() == 0


def test_operator_qr_404_for_missing_profile(
    client: APIClient, manager_user
) -> None:  # type: ignore[no-untyped-def]
    """A random UUID returns 404 (DRF's default), not 500."""
    import uuid

    client.force_authenticate(manager_user)
    response = client.get(f"/api/v1/invigilators/profiles/{uuid.uuid4()}/qr.png/")
    assert response.status_code == 404
