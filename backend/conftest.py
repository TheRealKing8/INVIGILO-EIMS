"""Pytest configuration and fixtures for the invigilo backend test suite.

The fixtures below are scoped to the smallest practical level so a single
test can run with a fresh database without paying the full setup cost.
"""
from __future__ import annotations

import os
from typing import Iterator

import pytest
from django.conf import settings
from rest_framework.test import APIClient

# Test settings must be active before any Django app loads.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "invigilo.settings.test")


@pytest.fixture
def api_client() -> APIClient:
    """Unauthenticated DRF APIClient."""
    return APIClient()


@pytest.fixture
def user_factory(db):  # type: ignore[no-untyped-def]
    """Factory for creating active, verified users.

    Usage:
        user_factory(email="alice@x.com", roles=["IN"])
    """
    from apps.accounts.services.users import create_user

    def _factory(email: str = "user@example.com", **kwargs):  # type: ignore[no-untyped-def]
        return create_user(email=email, **kwargs)

    return _factory


@pytest.fixture(autouse=True)
def _enable_db_access_for_all_tests(db):  # type: ignore[no-untyped-def]
    """Allow every test to use the database.

    This is a no-op marker; pytest-django applies the `db` fixture to make
    the test database available. We keep it explicit for IDEs.
    """
    yield


@pytest.fixture
def freeze_time():
    """Freeze time for tests that depend on the wall clock."""
    from freezegun import freeze_time as _freeze_time

    return _freeze_time
