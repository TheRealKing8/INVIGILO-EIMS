"""Phase 21 tests — multi-role login, role-pick, password minimum, register defaults.

The auth flow gained a new step in Phase 21: users with more than one
active role get a ``login_token`` and a list of available roles. They
pick one (the JWT is reissued with that role baked into the claim), or
they hand off to OTP if the chosen role is staff. Single-role users
skip the picker entirely.

These tests cover:

* single-role user → token pair (existing flow, regression check)
* multi-role user → role-pick payload with available_roles + login_token
* select-role → token pair when chosen role is non-staff
* select-role → requires_otp payload when chosen role is staff
* select-role with role the user doesn't hold → 422
* select-role with consumed/expired login_token → 400
* register with no roles → STUDENT (server-side default)
* register with staff role in body → silently dropped
* 6-char password with 3 classes → accepted
* 5-char password → rejected
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import LoginToken, Role, UserRole
from apps.accounts.services import auth as auth_service


pytestmark = pytest.mark.django_db

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ensure_role(code: str, name: str) -> Role:
    role, _ = Role.objects.update_or_create(
        code=code, defaults={"name": name, "is_active": True}
    )
    return role


def _make_user(email: str, roles: list[str]) -> User:
    user = User.objects.create_user(
        email=email,
        full_name=email.split("@")[0].title(),
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    for code in roles:
        UserRole.objects.create(user=user, role=_ensure_role(code, code.title()))
    return user


# ---------------------------------------------------------------------------
# Login — multi-role path
# ---------------------------------------------------------------------------
def test_login_single_role_returns_token_pair(
    client: APIClient, student_user: User
) -> None:
    """Single-role user gets the token pair directly — no role-pick step.

    Regression check for Phase 21: the new branch must not break the
    existing single-role flow.
    """
    response = client.post(
        reverse("auth:auth-login"),
        {"email": "student@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert "access" in body
    assert body["user"]["role"] == "STUDENT"
    assert "requires_role_pick" not in body


def test_login_multi_role_returns_role_pick(client: APIClient) -> None:
    """A user with two roles gets the role-pick payload back.

    The payload shape:

    * ``requires_role_pick: true``
    * ``available_roles``: list of ``{code, name, description}``
    * ``login_token``: a 5-min, single-use proof-of-credentials token
    """
    user = _make_user("multi@x.com", ["STUDENT", "INVIGILATOR"])
    response = client.post(
        reverse("auth:auth-login"),
        {"email": "multi@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requires_role_pick"] is True
    assert "login_token" in body
    assert "access" not in body  # not yet — picker first.
    codes = [r["code"] for r in body["available_roles"]]
    # Ordered by precedence — INVIGILATOR (higher) before STUDENT.
    assert codes == ["INVIGILATOR", "STUDENT"]
    # Each entry carries a description.
    for entry in body["available_roles"]:
        assert "code" in entry
        assert "name" in entry
        assert "description" in entry
    # The login_token is persisted as a hash, single-use, 5-min TTL.
    raw = body["login_token"]
    row = LoginToken.objects.get(token_hash=auth_service._hash_token(raw))
    assert row.is_usable() is True
    assert row.user_id == user.id


def test_login_multi_role_staff_also_returns_otp_token(client: APIClient) -> None:
    """A multi-role user whose primary is staff also gets an otp_token
    in the first response.

    The frontend can pre-emptively show the OTP step UI when the user
    picks a staff role — the ``otp_token`` is harmless if they don't.
    """
    _make_user("hod_inv@x.com", ["HEAD_OF_DEPARTMENT", "INVIGILATOR"])
    response = client.post(
        reverse("auth:auth-login"),
        {"email": "hod_inv@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requires_role_pick"] is True
    assert body.get("requires_otp") is True
    assert "otp_token" in body


def test_login_multi_role_non_staff_does_not_include_otp(client: APIClient) -> None:
    """A user with multiple non-staff roles does not get an otp_token
    on the first step — OTP only matters for staff picks, and we don't
    know what they'll pick yet.
    """
    # Drop the student fixture's seeded role and re-add STUDENT + GUEST
    # so the user is multi-role but neither is staff.
    _make_user("both_end@x.com", ["STUDENT", "GUEST"])
    response = client.post(
        reverse("auth:auth-login"),
        {"email": "both_end@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requires_role_pick"] is True
    assert "otp_token" not in body


# ---------------------------------------------------------------------------
# Select-role — the second step
# ---------------------------------------------------------------------------
def test_select_role_non_staff_returns_token_pair(client: APIClient) -> None:
    """Picking a non-staff role on the second step returns the token
    pair directly (no OTP)."""
    user = _make_user("multi2@x.com", ["STUDENT", "INVIGILATOR"])
    login = client.post(
        reverse("auth:auth-login"),
        {"email": "multi2@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    login_token = login.json()["login_token"]

    response = client.post(
        reverse("auth:auth-select-role"),
        {"login_token": login_token, "role_code": "STUDENT"},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert "access" in body
    assert body["user"]["role"] == "STUDENT"
    assert body["user"]["active_role"] == "STUDENT"
    # The login_token is consumed.
    row = LoginToken.objects.get(token_hash=auth_service._hash_token(login_token))
    assert row.is_usable() is False


def test_select_role_staff_returns_otp(client: APIClient) -> None:
    """Picking a staff role on the second step hands off to OTP."""
    _make_user("multi3@x.com", ["HEAD_OF_DEPARTMENT", "STUDENT"])
    login = client.post(
        reverse("auth:auth-login"),
        {"email": "multi3@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    login_token = login.json()["login_token"]

    response = client.post(
        reverse("auth:auth-select-role"),
        {"login_token": login_token, "role_code": "HEAD_OF_DEPARTMENT"},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requires_otp"] is True
    assert "otp_token" in body
    assert body["role"] == "HEAD_OF_DEPARTMENT"
    # No access token yet — must complete OTP.
    assert "access" not in body


def test_select_role_rejects_unheld_role(client: APIClient) -> None:
    """A role the user doesn't actually hold is rejected with 422.

    Prevents a stale picker card from being replayed against a role
    the user has since been removed from. The login_token must NOT
    be consumed on a 422 — the user should be able to retry with a
    role they actually hold without re-authenticating from scratch.
    """
    _make_user("multi4@x.com", ["STUDENT", "INVIGILATOR"])
    login = client.post(
        reverse("auth:auth-login"),
        {"email": "multi4@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    login_token = login.json()["login_token"]

    response = client.post(
        reverse("auth:auth-select-role"),
        {"login_token": login_token, "role_code": "SYSTEM_ADMINISTRATOR"},
        format="json",
    )
    assert response.status_code == 422

    # Token is still usable — retry with a held role succeeds.
    row = LoginToken.objects.get(token_hash=auth_service._hash_token(login_token))
    assert row.is_usable() is True

    retry = client.post(
        reverse("auth:auth-select-role"),
        {"login_token": login_token, "role_code": "STUDENT"},
        format="json",
    )
    assert retry.status_code == 200, retry.json()


def test_select_role_rejects_consumed_token(client: APIClient) -> None:
    """A login_token can only be used once. The second use is 400."""
    _make_user("multi5@x.com", ["STUDENT", "INVIGILATOR"])
    login = client.post(
        reverse("auth:auth-login"),
        {"email": "multi5@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    login_token = login.json()["login_token"]

    # First use — succeeds.
    first = client.post(
        reverse("auth:auth-select-role"),
        {"login_token": login_token, "role_code": "STUDENT"},
        format="json",
    )
    assert first.status_code == 200

    # Second use — fails.
    second = client.post(
        reverse("auth:auth-select-role"),
        {"login_token": login_token, "role_code": "INVIGILATOR"},
        format="json",
    )
    assert second.status_code == 400


def test_select_role_rejects_unknown_token(client: APIClient) -> None:
    """An unknown login_token is 400, not 404, to avoid probing for
    which tokens exist."""
    response = client.post(
        reverse("auth:auth-select-role"),
        {"login_token": "bogus", "role_code": "STUDENT"},
        format="json",
    )
    assert response.status_code == 400


def test_select_role_bakes_role_into_jwt(client: APIClient) -> None:
    """The JWT issued by select-role carries the *chosen* role, not
    the user's primary role — so a HOD who picked STUDENT can read
    student data through their STUDENT role on subsequent requests.
    """
    _make_user("multi6@x.com", ["HEAD_OF_DEPARTMENT", "STUDENT"])
    login = client.post(
        reverse("auth:auth-login"),
        {"email": "multi6@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    login_token = login.json()["login_token"]

    response = client.post(
        reverse("auth:auth-select-role"),
        {"login_token": login_token, "role_code": "STUDENT"},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == "STUDENT"
    assert body["user"]["active_role"] == "STUDENT"

    # The JWT claim agrees.
    import jwt
    from django.conf import settings

    payload = jwt.decode(
        body["access"],
        settings.SIMPLE_JWT["SIGNING_KEY"],
        algorithms=[settings.SIMPLE_JWT["ALGORITHM"]],
        audience=settings.SIMPLE_JWT["AUDIENCE"],
        issuer=settings.SIMPLE_JWT["ISSUER"],
    )
    assert payload["role"] == "STUDENT"


# ---------------------------------------------------------------------------
# Register — STUDENT default + privilege allowlist
# ---------------------------------------------------------------------------
def test_register_defaults_to_student_role(client: APIClient) -> None:
    """A self-registered user with no roles in the body lands on
    STUDENT — the dashboard router needs a role to branch on.
    """
    response = client.post(
        reverse("auth:auth-register"),
        {"full_name": "New", "email": "newr@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    assert response.status_code == 201
    user = User.objects.get(email="newr@x.com")
    assert user.primary_role_code == "STUDENT"
    assert user.has_role("STUDENT") is True
    assert user.has_role("EXAMINATION_OFFICER") is False


def test_register_drops_privileged_roles_silently(client: APIClient) -> None:
    """A self-registration attempt to land on staff roles is silently
    demoted to a safe role — the public path can't elevate itself.

    Returning 422 would let an attacker probe which role codes exist
    (since the server would say "unknown code" for non-existent
    ones). Silent demotion matches the existing ``validate_roles``
    contract that the serializer already uses for known codes.

    We send only the privileged role (no GUEST) so the final
    fallback to STUDENT is the one that takes effect.
    """
    response = client.post(
        reverse("auth:auth-register"),
        {
            "full_name": "Priv",
            "email": "prv@x.com",
            "password": "S3cur3Passw0rd!",
            "roles": ["EXAMINATION_OFFICER"],
        },
        format="json",
    )
    assert response.status_code == 201
    user = User.objects.get(email="prv@x.com")
    # Privileged roles are dropped; the final fallback lands the
    # user on STUDENT.
    assert user.has_role("EXAMINATION_OFFICER") is False
    assert user.has_role("SYSTEM_ADMINISTRATOR") is False
    assert user.primary_role_code == "STUDENT"


# ---------------------------------------------------------------------------
# Password minimum — 6 chars
# ---------------------------------------------------------------------------
def test_password_minimum_6_chars_accepted(client: APIClient) -> None:
    """A 6-character password that satisfies 3-of-4 complexity is
    accepted. Regression check for the Phase 21 lowering from 12.
    """
    response = client.post(
        reverse("auth:auth-register"),
        {
            "full_name": "Six Char",
            "email": "six@x.com",
            "password": "Abcde1",
        },
        format="json",
    )
    assert response.status_code == 201, response.json()


def test_password_5_chars_rejected(client: APIClient) -> None:
    """A 5-character password (below the new minimum) is rejected.

    Server returns 422 (the validation_failed contract used by
    :class:`apps.core.exceptions.ValidationFailedError`).
    """
    response = client.post(
        reverse("auth:auth-register"),
        {
            "full_name": "Five Char",
            "email": "five@x.com",
            "password": "Abcd1",
        },
        format="json",
    )
    assert response.status_code == 422
    body = response.json()
    # The validator's error message keys off the "password" field
    # (we used ``detail`` only at the auth layer for opaque failures).
    assert "password" in str(body).lower() or "characters" in str(body).lower()


def test_password_8_chars_2_classes_rejected(client: APIClient) -> None:
    """8 chars but only 2 of 4 classes is still rejected — the
    complexity rule is unchanged. ``aaaaaaaa`` has only lowercase.
    """
    response = client.post(
        reverse("auth:auth-register"),
        {
            "full_name": "Two Class",
            "email": "twoc@x.com",
            "password": "aaaaaaaa",
        },
        format="json",
    )
    assert response.status_code == 422
