"""Tests for the admin two-step login.

* Admin (``SYSTEM_ADMINISTRATOR``) login returns
  ``{requires_otp: true, otp_token: "..."}`` with no JWT pair.
* Other roles skip the OTP step and get a JWT pair straight away.
* ``POST /auth/verify-otp/`` with the right code returns the JWT pair.
* ``POST /auth/verify-otp/`` with the wrong code returns 400, the
  attempt counter increments, and after five failures the OTP row is
  revoked.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import LoginOTP, Role, UserRole
from apps.accounts.services import auth as auth_service


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
def admin_user(admin_role: Role) -> User:
    user = User.objects.create_user(
        email="admin@x.com",
        full_name="Admin",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=admin_role)
    return user


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
def test_admin_login_returns_requires_otp(client: APIClient, admin_user: User) -> None:
    from django.core import mail

    response = client.post(
        reverse("auth:auth-login"),
        {"email": "admin@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requires_otp"] is True
    assert isinstance(body["otp_token"], str) and len(body["otp_token"]) > 16
    assert "access" not in body
    # Exactly one active OTP row for this user.
    assert LoginOTP.objects.filter(user=admin_user, consumed_at__isnull=True).count() == 1
    # The OTP email was actually sent (in dev this is the console
    # backend, in tests it's locmem). ``CELERY_TASK_ALWAYS_EAGER``
    # makes the ``.delay()`` call run synchronously so the mailbox
    # already has the message by the time this assertion runs.
    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert sent.to == [admin_user.email]
    # The 6-digit code is in the body. We don't assert the exact
    # value (it's random) — we just check that a 6-digit token
    # appears somewhere in the rendered text.
    import re

    assert re.search(r"\b\d{6}\b", sent.body) is not None


def test_invigilator_login_skips_otp(client: APIClient, verified_user: User) -> None:
    response = client.post(
        reverse("auth:auth-login"),
        {"email": "alice@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert "access" in body
    assert "requires_otp" not in body
    # No OTP row was created for the invigilator.
    assert not LoginOTP.objects.filter(user=verified_user).exists()


# ---------------------------------------------------------------------------
# Verify OTP
# ---------------------------------------------------------------------------
def test_otp_verify_with_correct_code_returns_tokens(client: APIClient, admin_user: User) -> None:
    # First step issues the OTP and stashes the code via the helper.
    otp_token, code = auth_service.issue_login_otp(admin_user)
    response = client.post(
        reverse("auth:auth-verify-otp"),
        {"otp_token": otp_token, "code": code},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert "access" in body
    assert body["user"]["email"] == "admin@x.com"
    # The row is now consumed.
    row = LoginOTP.objects.get(otp_token=otp_token)
    assert row.consumed_at is not None


def test_otp_verify_with_wrong_code_rejects_and_counts(client: APIClient, admin_user: User) -> None:
    otp_token, _ = auth_service.issue_login_otp(admin_user)
    response = client.post(
        reverse("auth:auth-verify-otp"),
        {"otp_token": otp_token, "code": "000000"},
        format="json",
    )
    assert response.status_code == 400
    row = LoginOTP.objects.get(otp_token=otp_token)
    assert row.attempts == 1
    assert row.consumed_at is None  # still usable after 1 miss


def test_otp_verify_revokes_after_max_attempts(client: APIClient, admin_user: User) -> None:
    """Five wrong codes in a row must revoke the row so the same
    ``otp_token`` can never be used again."""
    otp_token, _ = auth_service.issue_login_otp(admin_user)
    for _ in range(LoginOTP.MAX_ATTEMPTS):
        response = client.post(
            reverse("auth:auth-verify-otp"),
            {"otp_token": otp_token, "code": "111111"},
            format="json",
        )
        assert response.status_code == 400
    row = LoginOTP.objects.get(otp_token=otp_token)
    assert row.attempts == LoginOTP.MAX_ATTEMPTS
    assert row.consumed_at is not None


def test_otp_verify_unknown_token_rejects(client: APIClient, admin_user: User) -> None:
    response = client.post(
        reverse("auth:auth-verify-otp"),
        {"otp_token": "definitely-not-real", "code": "123456"},
        format="json",
    )
    assert response.status_code == 400


def test_otp_reissue_revokes_prior_otp(client: APIClient, admin_user: User) -> None:
    """A second login while the first OTP is still active should
    revoke the older one and create a fresh row, so the most recent
    email is the one that matters."""
    first_token, _ = auth_service.issue_login_otp(admin_user)
    second_token, _ = auth_service.issue_login_otp(admin_user)
    first_row = LoginOTP.objects.get(otp_token=first_token)
    assert first_row.consumed_at is not None
    # The second row is fresh and unconsumed.
    second_row = LoginOTP.objects.get(otp_token=second_token)
    assert second_row.consumed_at is None
    # And only one unconsumed row exists for the user.
    assert (
        LoginOTP.objects.filter(user=admin_user, consumed_at__isnull=True).count() == 1
    )
