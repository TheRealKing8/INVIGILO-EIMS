"""Tests for the auth flow — login, refresh, logout, password change/reset,
email verification, lockout.

The flow is exercised through the DRF endpoints so the URL wiring and
serializers are covered alongside the service layer.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import EmailVerification, PasswordReset, RefreshToken, Role, UserRole
from apps.accounts.services import auth as auth_service


pytestmark = pytest.mark.django_db

User = get_user_model()


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
def test_login_returns_token_pair(client: APIClient, student_user: User) -> None:
    response = client.post(
        reverse("auth:auth-login"),
        {"email": "student@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert "access" in body
    assert "refresh" in body
    assert body["user"]["email"] == "student@x.com"
    assert body["user"]["role"] == "STUDENT"


def test_login_response_includes_permissions_claim(
    client: APIClient, student_user: User
) -> None:
    """The login response must include a ``permissions`` list on the user.

    STUDENT skips the OTP step so we get the JWT pair in one
    round-trip. The list is the union of permission codenames granted
    across all of the user's active roles.
    """
    response = client.post(
        reverse("auth:auth-login"),
        {"email": "student@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["user"]["permissions"], list)
    # Student's seeded grants (see apps/accounts/seed.py).
    assert "accounts.profile.update_own" in body["user"]["permissions"]
    assert "exam.session.view_own" in body["user"]["permissions"]
    # An admin-only permission should NOT be on this student's list.
    assert "settings.update" not in body["user"]["permissions"]


def test_login_access_token_carries_permissions_claim(
    client: APIClient, student_user: User
) -> None:
    """The encoded JWT must carry the same ``permissions`` claim.

    The frontend reads it from ``localStorage`` (saved at login) and
    uses it across page navigations. The claim must match the response
    payload so client and server are always in agreement. STUDENT
    skips OTP so the access token is in the login response body.
    """
    import jwt
    from django.conf import settings

    response = client.post(
        reverse("auth:auth-login"),
        {"email": "student@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    access = response.json()["access"]
    payload = jwt.decode(
        access,
        settings.SIMPLE_JWT["SIGNING_KEY"],
        algorithms=[settings.SIMPLE_JWT["ALGORITHM"]],
        audience=settings.SIMPLE_JWT["AUDIENCE"],
        issuer=settings.SIMPLE_JWT["ISSUER"],
    )
    assert payload["role"] == "STUDENT"
    assert "permissions" in payload
    assert "accounts.profile.update_own" in payload["permissions"]
    assert "settings.update" not in payload["permissions"]


def test_login_wrong_password_returns_401(client: APIClient, verified_user: User) -> None:
    response = client.post(
        reverse("auth:auth-login"),
        {"email": "alice@x.com", "password": "wrong"},
        format="json",
    )
    assert response.status_code == 401
    verified_user.refresh_from_db()
    assert verified_user.failed_login_count == 1


def test_login_unknown_user_returns_401(client: APIClient) -> None:
    response = client.post(
        reverse("auth:auth-login"),
        {"email": "nobody@x.com", "password": "x"},
        format="json",
    )
    assert response.status_code == 401


def test_login_unverified_email_returns_403(client: APIClient) -> None:
    User.objects.create_user(email="n@x.com", full_name="N", password="S3cur3Passw0rd!")
    response = client.post(
        reverse("auth:auth-login"),
        {"email": "n@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    assert response.status_code == 403
    assert response.json()["code"] == "email_unverified"


def test_login_locked_account_returns_403(client: APIClient, verified_user: User) -> None:
    from django.utils import timezone

    verified_user.locked_until = timezone.now() + timezone.timedelta(minutes=10)
    verified_user.save()
    response = client.post(
        reverse("auth:auth-login"),
        {"email": "alice@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    assert response.status_code == 403


def test_register_creates_user_and_returns_tokens(client: APIClient) -> None:
    response = client.post(
        reverse("auth:auth-register"),
        {"full_name": "New User", "email": "new@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert "access" in body
    assert body["user"]["email"] == "new@x.com"
    assert User.objects.filter(email="new@x.com").exists()


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------
def test_refresh_rotates_and_revokes_old_token(client: APIClient, verified_user: User) -> None:
    pair = auth_service.issue_token_pair(verified_user)
    old_refresh = pair["refresh"]

    response = client.post(
        reverse("auth:auth-refresh"),
        {"refresh": old_refresh},
        format="json",
    )
    assert response.status_code == 200
    new_pair = response.json()
    assert new_pair["refresh"] != old_refresh
    assert RefreshToken.objects.get(token_hash=auth_service._hash_token(old_refresh)).revoked_at is not None


def test_refresh_with_revoked_token_rejects(client: APIClient, verified_user: User) -> None:
    pair = auth_service.issue_token_pair(verified_user)
    auth_service.revoke_refresh(pair["refresh"])
    response = client.post(
        reverse("auth:auth-refresh"),
        {"refresh": pair["refresh"]},
        format="json",
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
def test_logout_revokes_refresh(client: APIClient, verified_user: User) -> None:
    pair = auth_service.issue_token_pair(verified_user)
    response = client.post(
        reverse("auth:auth-logout"),
        {"refresh": pair["refresh"]},
        format="json",
    )
    assert response.status_code == 204
    assert RefreshToken.objects.get(token_hash=auth_service._hash_token(pair["refresh"])).revoked_at is not None


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------
def test_email_verification_round_trip(client: APIClient) -> None:
    user = User.objects.create_user(email="v@x.com", full_name="V", password="S3cur3Passw0rd!")
    token = auth_service.issue_email_verification(user)
    response = client.post(
        reverse("auth:auth-verify-confirm"),
        {"token": token},
        format="json",
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.is_email_verified is True
    assert EmailVerification.objects.get(token_hash=auth_service._hash_token(token)).used_at is not None


def test_email_verification_unknown_token_returns_404(client: APIClient) -> None:
    response = client.post(
        reverse("auth:auth-verify-confirm"),
        {"token": "nope"},
        format="json",
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------
def test_password_reset_request_is_idempotent_for_unknown_email(client: APIClient) -> None:
    response = client.post(
        reverse("auth:auth-password-reset-request"),
        {"email": "nobody@x.com"},
        format="json",
    )
    assert response.status_code == 202


def test_password_reset_round_trip_revokes_refresh_tokens(
    client: APIClient, verified_user: User
) -> None:
    pair = auth_service.issue_token_pair(verified_user)
    token = auth_service.issue_password_reset(verified_user.email)
    assert token is not None
    response = client.post(
        reverse("auth:auth-password-reset-confirm"),
        {"token": token, "new_password": "N3wS3cur3Pass!"},
        format="json",
    )
    assert response.status_code == 204
    verified_user.refresh_from_db()
    assert verified_user.check_password("N3wS3cur3Pass!")
    assert PasswordReset.objects.get(token_hash=auth_service._hash_token(token)).used_at is not None
    # Refresh tokens are revoked.
    assert (
        RefreshToken.objects.get(token_hash=auth_service._hash_token(pair["refresh"])).revoked_at
        is not None
    )


def test_password_reset_confirm_rejects_unknown_token(client: APIClient) -> None:
    """A bogus token is 404 — we don't tell an attacker the token
    *format*, but the row genuinely doesn't exist, so NotFoundError
    is the right code (matches the "explore then exploit" pattern
    of other endpoints).
    """
    response = client.post(
        reverse("auth:auth-password-reset-confirm"),
        {"token": "bogus-token", "new_password": "Abcde1"},
        format="json",
    )
    assert response.status_code == 404


def test_password_reset_confirm_rejects_expired_token(
    client: APIClient, verified_user: User
) -> None:
    """A token past its expires_at is rejected with 422.

    Phase 22 — the failure path was previously untested; a bug here
    would silently break every user whose link sat in their inbox
    for more than 30 minutes.
    """
    from django.utils import timezone

    token = auth_service.issue_password_reset(verified_user.email)
    assert token is not None
    # Backdate the row so the lookup sees an expired token.
    PasswordReset.objects.filter(token_hash=auth_service._hash_token(token)).update(
        expires_at=timezone.now() - timezone.timedelta(seconds=1)
    )
    response = client.post(
        reverse("auth:auth-password-reset-confirm"),
        {"token": token, "new_password": "Abcde1"},
        format="json",
    )
    assert response.status_code == 422
    assert "expired or been used" in response.json()["detail"]


def test_password_reset_confirm_rejects_consumed_token(
    client: APIClient, verified_user: User
) -> None:
    """A token can only be used once. The second use is 422.

    The service deliberately collapses "expired" and "already used"
    into the same opaque message so a successful-then-replay attack
    can't tell the difference.
    """
    token = auth_service.issue_password_reset(verified_user.email)
    assert token is not None

    first = client.post(
        reverse("auth:auth-password-reset-confirm"),
        {"token": token, "new_password": "Abcde1"},
        format="json",
    )
    assert first.status_code == 204

    second = client.post(
        reverse("auth:auth-password-reset-confirm"),
        {"token": token, "new_password": "Differnt2"},
        format="json",
    )
    assert second.status_code == 422
    assert "expired or been used" in second.json()["detail"]


def test_password_reset_rejects_weak_new_password(
    client: APIClient, verified_user: User
) -> None:
    """A reset that arrives with a too-short or too-simple new password
    is rejected with 422.

    Phase 22 — Phase 21 dropped the minimum from 12 to 6 chars, but
    only the *register* path was re-tested at the new floor. This
    test pins the same rule through the reset-confirm path so a
    future bump (or a silent regression in the validator wiring)
    surfaces here.
    """
    token = auth_service.issue_password_reset(verified_user.email)
    assert token is not None

    # 5 chars, single class — fails the length and complexity rules.
    response = client.post(
        reverse("auth:auth-password-reset-confirm"),
        {"token": token, "new_password": "short"},
        format="json",
    )
    assert response.status_code == 422
    # The token must NOT be consumed on a weak-password rejection —
    # the user should be able to retry with a stronger password on
    # the same link.
    assert (
        PasswordReset.objects.get(token_hash=auth_service._hash_token(token)).used_at is None
    )


# ---------------------------------------------------------------------------
# Password change (authenticated)
# ---------------------------------------------------------------------------
def test_password_change_requires_current(client: APIClient, verified_user: User) -> None:
    client.force_authenticate(verified_user)
    response = client.post(
        reverse("auth:auth-password-change"),
        {"current": "wrong", "new": "An0therS3cur3Pass!"},
        format="json",
    )
    assert response.status_code == 422


def test_password_change_succeeds(client: APIClient, verified_user: User) -> None:
    client.force_authenticate(verified_user)
    response = client.post(
        reverse("auth:auth-password-change"),
        {"current": "S3cur3Passw0rd!", "new": "An0therS3cur3Pass!"},
        format="json",
    )
    assert response.status_code == 204
    verified_user.refresh_from_db()
    assert verified_user.check_password("An0therS3cur3Pass!")


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
def test_me_returns_serialized_user(client: APIClient, verified_user: User) -> None:
    client.force_authenticate(verified_user)
    response = client.get(reverse("auth:auth-me"))
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "alice@x.com"
    assert body["primary_role"] == "INVIGILATOR"
    assert any(r["code"] == "INVIGILATOR" for r in body["roles"])


def test_me_update_partial(client: APIClient, verified_user: User) -> None:
    client.force_authenticate(verified_user)
    response = client.patch(
        reverse("auth:auth-me-update"),
        {"phone": "+1-555-0100", "time_zone": "Africa/Nairobi"},
        format="json",
    )
    assert response.status_code == 200
    verified_user.refresh_from_db()
    assert verified_user.phone == "+1-555-0100"
    assert verified_user.time_zone == "Africa/Nairobi"


# ---------------------------------------------------------------------------
# Lockout
# ---------------------------------------------------------------------------
def test_lockout_after_threshold(settings) -> None:  # type: ignore[no-untyped-def]
    settings.LOCKOUT_THRESHOLD = 2
    settings.LOCKOUT_DURATION_MINUTES = 5
    user = User.objects.create_user(
        email="lock@x.com", full_name="L", password="S3cur3Passw0rd!", is_email_verified=True
    )
    # Two wrong logins should lock the account.
    for _ in range(2):
        from apps.core.exceptions import AuthenticationError

        with pytest.raises(AuthenticationError):
            auth_service.authenticate("lock@x.com", "wrong")
    user.refresh_from_db()
    assert user.is_locked() is True
    # A subsequent attempt with the correct password is refused.
    from apps.core.exceptions import PermissionDeniedError

    with pytest.raises(PermissionDeniedError):
        auth_service.authenticate("lock@x.com", "S3cur3Passw0rd!")
