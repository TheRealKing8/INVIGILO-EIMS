"""Tests for the .ics calendar export."""
from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_unauthenticated_returns_401(client: APIClient) -> None:
    response = client.get(reverse("calendar:calendar-feed"))
    assert response.status_code == 401


def test_ics_export_returns_attachment(
    client: APIClient, verified_user, grant_permission, allocation
) -> None:
    grant_permission(verified_user, "notification.view_own")
    client.force_authenticate(verified_user)

    response = client.get(reverse("calendar:calendar-feed"))
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/calendar")
    assert "attachment" in response["Content-Disposition"]

    body = response.content.decode("utf-8")
    assert body.startswith("BEGIN:VCALENDAR")
    assert "END:VCALENDAR" in body
    # The session in the ``session`` fixture has course code "C" and
    # title "C" — both end up in SUMMARY.
    assert "BEGIN:VEVENT" in body
    assert "C — C" in body or "C" in body
    # DTSTART must be in the .ics UTC format.
    assert "DTSTART:" in body
    assert "DTEND:" in body


def test_ics_empty_for_user_with_no_sessions(
    client: APIClient, verified_user, grant_permission
) -> None:
    """A user with no allocations gets a valid empty calendar."""
    grant_permission(verified_user, "notification.view_own")
    client.force_authenticate(verified_user)

    response = client.get(reverse("calendar:calendar-feed"))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert body.startswith("BEGIN:VCALENDAR")
    assert body.rstrip("\r\n").endswith("END:VCALENDAR")
    assert "BEGIN:VEVENT" not in body


def test_build_ics_escapes_special_characters() -> None:
    """The hand-rolled builder must escape RFC 5545 special chars."""
    from apps.notifications.services import build_ics

    class _Stub:
        class _Course:
            code = "CS101"
            title = "Intro, Basics; with\\backslash"

        course = _Course()

        class _Room:
            class _Building:
                code = "ENG"

            building = _Building()
            code = "A1"

        room = _Room()
        starts_at = datetime(2026, 8, 1, 9, 0, tzinfo=dt_timezone.utc)
        ends_at = datetime(2026, 8, 1, 11, 0, tzinfo=dt_timezone.utc)
        special_requirements = "Quiet room; no phones"
        id = "test-id"

    body = build_ics([_Stub()], calendar_name="Test; Calendar, with stuff")
    # Comma + semicolon must be backslash-escaped.
    assert r"Intro\, Basics\; with\\backslash" in body
    assert r"Test\; Calendar\, with stuff" in body
    assert r"Quiet room\; no phones" in body
