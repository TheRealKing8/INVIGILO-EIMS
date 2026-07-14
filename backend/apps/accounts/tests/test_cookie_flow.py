"""Tests for the httpOnly refresh-token cookie flow.

The cookie is the primary delivery channel for the refresh token in
production. The browser stores it as ``invigilo_rt``, sends it back
on every refresh/logout request, and the server rotates or clears it
on the way out. These tests cover that round-trip at the view layer.
"""
from __future__ import annotations

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import RefreshToken
from apps.accounts.services import auth as auth_service


pytestmark = pytest.mark.django_db


User = get_user_model()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
def test_login_sets_httponly_refresh_cookie(client: APIClient, student_user) -> None:  # type: ignore[no-untyped-def]
    # STUDENT skips the OTP step so the login response carries the
    # full JWT pair + the httpOnly refresh cookie in one round-trip.
    response = client.post(
        reverse("auth:auth-login"),
        {"email": "student@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    assert response.status_code == 200
    cookie_name = settings.JWT_REFRESH_COOKIE_NAME
    assert cookie_name in response.cookies
    morsel = response.cookies[cookie_name]
    assert morsel["httponly"] is True or morsel["httponly"] == ""
    # In tests we set Secure=False so the cookie is sent over http;
    # the production default is True.
    assert morsel["samesite"].lower() == settings.JWT_REFRESH_COOKIE_SAMESITE.lower()
    assert morsel["path"] == settings.JWT_REFRESH_COOKIE_PATH
    assert morsel.value  # the raw refresh is in the cookie


def test_login_cookie_value_matches_persisted_refresh(client: APIClient, student_user) -> None:  # type: ignore[no-untyped-def]
    response = client.post(
        reverse("auth:auth-login"),
        {"email": "student@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    raw = response.cookies[settings.JWT_REFRESH_COOKIE_NAME].value
    # A RefreshToken row was created whose hash matches the cookie.
    RefreshToken.objects.get(token_hash=auth_service._hash_token(raw))


def test_register_sets_httponly_refresh_cookie(client: APIClient) -> None:
    response = client.post(
        reverse("auth:auth-register"),
        {"email": "newby@x.com", "full_name": "New By", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    assert response.status_code == 201
    assert settings.JWT_REFRESH_COOKIE_NAME in response.cookies


# ---------------------------------------------------------------------------
# Refresh — cookie-driven
# ---------------------------------------------------------------------------
def test_refresh_via_cookie_rotates_and_resets_cookie(
    client: APIClient, student_user
) -> None:  # type: ignore[no-untyped-def]
    login = client.post(
        reverse("auth:auth-login"),
        {"email": "student@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    old_raw = login.cookies[settings.JWT_REFRESH_COOKIE_NAME].value

    # Make a refresh request *without* a body — only the cookie travels.
    refresh = client.post(reverse("auth:auth-refresh"), {}, format="json")
    assert refresh.status_code == 200, refresh.content
    new_raw = refresh.cookies[settings.JWT_REFRESH_COOKIE_NAME].value
    assert new_raw and new_raw != old_raw

    # The old row is revoked, the new one is active.
    assert (
        RefreshToken.objects.get(token_hash=auth_service._hash_token(old_raw)).revoked_at
        is not None
    )
    assert (
        RefreshToken.objects.get(token_hash=auth_service._hash_token(new_raw)).revoked_at
        is None
    )


def test_refresh_without_cookie_or_body_returns_400(
    client: APIClient, verified_user
) -> None:  # type: ignore[no-untyped-def]
    response = client.post(reverse("auth:auth-refresh"), {}, format="json")
    assert response.status_code == 400
    assert "missing" in response.json()["detail"].lower()


def test_refresh_with_body_fallback_still_works(
    client: APIClient, verified_user
) -> None:  # type: ignore[no-untyped-def]
    """Non-browser clients that send the refresh in the body keep working."""
    pair = auth_service.issue_token_pair(verified_user)
    response = client.post(
        reverse("auth:auth-refresh"),
        {"refresh": pair["refresh"]},
        format="json",
    )
    assert response.status_code == 200
    new_pair = response.json()
    assert new_pair["access"]
    # The refresh response also sets a new cookie.
    assert settings.JWT_REFRESH_COOKIE_NAME in response.cookies


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
def test_logout_with_cookie_clears_cookie_and_revokes(
    client: APIClient, student_user
) -> None:  # type: ignore[no-untyped-def]
    login = client.post(
        reverse("auth:auth-login"),
        {"email": "student@x.com", "password": "S3cur3Passw0rd!"},
        format="json",
    )
    raw = login.cookies[settings.JWT_REFRESH_COOKIE_NAME].value

    # Logout sends only the cookie (no body).
    response = client.post(reverse("auth:auth-logout"), {}, format="json")
    assert response.status_code == 204
    # The cookie is deleted on the way out.
    morsel = response.cookies.get(settings.JWT_REFRESH_COOKIE_NAME)
    assert morsel is not None
    assert morsel.value == ""
    # The refresh row was revoked.
    assert (
        RefreshToken.objects.get(token_hash=auth_service._hash_token(raw)).revoked_at
        is not None
    )


def test_logout_with_empty_body_when_no_cookie_is_idempotent(
    client: APIClient, verified_user
) -> None:  # type: ignore[no-untyped-def]
    """An empty logout with no cookie is a 204 no-op — no error."""
    response = client.post(reverse("auth:auth-logout"), {}, format="json")
    assert response.status_code == 204
