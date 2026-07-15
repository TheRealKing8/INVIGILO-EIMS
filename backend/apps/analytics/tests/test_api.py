"""Tests for the analytics summary endpoint.

Eight tests, organised by behaviour:

* Authentication / permission gates (1-2)
* Officer sees everything (3)
* Invigilator sees a scoped workload (4-5)
* Edge cases (6-8)
"""
from __future__ import annotations

from datetime import date as _date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.allocations.models import Allocation
from apps.attendance.models import CheckIn
from apps.incidents.models import Incident

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def bare_user(db):  # type: ignore[no-untyped-def]
    """A confirmed, active user with no roles and no permissions.

    Used for the "no analytics.view codename" 403 test. The
    ``verified_user`` fixture below is INVIGILATOR + the codename
    (via ``grant_permission``), which is the wrong shape for a
    403 test.
    """
    return User.objects.create_user(
        email="bare@x.com",
        full_name="Bare User",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )


# ---------------------------------------------------------------------------
# Auth + permission
# ---------------------------------------------------------------------------
def test_unauthenticated_returns_401(client: APIClient) -> None:
    response = client.get(reverse("analytics:analytics-summary"))
    assert response.status_code == 401


def test_authenticated_user_without_codename_returns_403(
    client: APIClient, bare_user
) -> None:
    """A user with no roles and no permissions gets 403."""
    client.force_authenticate(bare_user)
    response = client.get(reverse("analytics:analytics-summary"))
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Operations view
# ---------------------------------------------------------------------------
def test_officer_sees_all_sections(
    client: APIClient, officer_user, grant_permission, period,
    session, second_session, allocation, allocation_run, checkin,
) -> None:
    """EO with the codename sees every section populated."""
    grant_permission(officer_user, "analytics.view")
    # Add a second invigilator + a second allocation so the workload
    # list has more than one row.
    from apps.accounts.models import Role, UserRole
    from apps.invigilators.models import InvigilatorProfile
    role, _ = Role.objects.update_or_create(
        code="INVIGILATOR", defaults={"name": "Invigilator", "is_active": True}
    )
    other = officer_user.__class__.objects.create_user(
        email="zoe@x.com", full_name="Zoe",
        password="S3cur3Passw0rd!", is_email_verified=True,
    )
    UserRole.objects.create(user=other, role=role)
    other_profile, _ = InvigilatorProfile.objects.update_or_create(
        user=other, defaults={"max_sessions_per_cycle": 10}
    )
    Allocation.objects.create(
        run=allocation_run, session=second_session,
        invigilator=other_profile, role="invigilator", status="confirmed",
    )
    # Add a high-severity incident in the active period so the
    # open-incident and severity counts move.
    Incident.objects.create(
        title="Power outage",
        body="Brief blackout",
        session=session,
        reporter=officer_user,
        severity="high",
        status="open",
    )

    client.force_authenticate(officer_user)
    response = client.get(reverse("analytics:analytics-summary"))
    assert response.status_code == 200
    data = response.json()

    # Period + coverage
    assert data["period_code"] == "AN1"
    assert data["coverage"] == 92.0  # 0.92 * 100
    # Counts
    assert data["upcoming_sessions_count"] >= 2
    assert data["checkins_today"] == 1
    assert data["late_count_today"] == 0
    assert data["open_incidents_count"] == 1
    # Workload: 2 rows (verified + zoe), each with allocated >= 1
    assert len(data["invigilator_workload"]) == 2
    workload_by_email = {row["email"]: row for row in data["invigilator_workload"]}
    assert "alice@x.com" in workload_by_email
    assert workload_by_email["alice@x.com"]["allocated"] == 1
    # Trend: 12 weekly buckets
    assert len(data["attendance_trend"]) == 12
    # Sessions-by-day: 7 days, day 1 (with both sessions) has count >= 2
    assert len(data["sessions_by_day"]) == 7
    # Severity: high == 1, all others zero
    assert data["incidents_by_severity"]["high"] == 1
    assert data["incidents_by_severity"]["low"] == 0
    assert data["incidents_by_severity"]["medium"] == 0
    assert data["incidents_by_severity"]["critical"] == 0


# ---------------------------------------------------------------------------
# Invigilator scope
# ---------------------------------------------------------------------------
def test_invigilator_workload_filtered_to_self(
    client: APIClient, verified_user, grant_permission, period, session,
    second_session, allocation_run, invigilator_profile,
) -> None:
    """INVIGILATOR role gets a workload list scoped to their own allocations.

    Two allocations in the same period — one for the verified user,
    one for a *different* invigilator. The verified user must see
    only the row that belongs to them, not the whole pool.
    """
    from apps.accounts.models import Role, UserRole
    from apps.invigilators.models import InvigilatorProfile
    role, _ = Role.objects.update_or_create(
        code="INVIGILATOR", defaults={"name": "Invigilator", "is_active": True}
    )
    other = verified_user.__class__.objects.create_user(
        email="dave@x.com", full_name="Dave",
        password="S3cur3Passw0rd!", is_email_verified=True,
    )
    UserRole.objects.create(user=other, role=role)
    other_profile, _ = InvigilatorProfile.objects.update_or_create(
        user=other, defaults={"max_sessions_per_cycle": 10}
    )
    Allocation.objects.create(
        run=allocation_run, session=session,
        invigilator=invigilator_profile, role="invigilator", status="confirmed",
    )
    Allocation.objects.create(
        run=allocation_run, session=second_session,
        invigilator=other_profile, role="invigilator", status="confirmed",
    )

    grant_permission(verified_user, "analytics.view")
    client.force_authenticate(verified_user)
    data = client.get(reverse("analytics:analytics-summary")).json()

    # Only the verified user's row.
    assert len(data["invigilator_workload"]) == 1
    assert data["invigilator_workload"][0]["email"] == "alice@x.com"
    assert data["invigilator_workload"][0]["allocated"] == 1


def test_invigilator_sees_overall_coverage(
    client: APIClient, verified_user, grant_permission, period,
    allocation_run, allocation,
) -> None:
    """INVIGILATOR sees the org-wide coverage tile even though their
    own workload is scoped."""
    grant_permission(verified_user, "analytics.view")
    client.force_authenticate(verified_user)
    data = client.get(reverse("analytics:analytics-summary")).json()
    assert data["coverage"] == 92.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
def test_no_active_period_returns_nulls(
    client: APIClient, officer_user, grant_permission, second_period,
) -> None:
    """Only an inactive period exists → coverage=null, counts all 0."""
    grant_permission(officer_user, "analytics.view")
    client.force_authenticate(officer_user)
    data = client.get(reverse("analytics:analytics-summary")).json()
    assert data["period_code"] is None
    assert data["coverage"] is None
    assert data["upcoming_sessions_count"] == 0
    assert data["checkins_today"] == 0
    assert data["late_count_today"] == 0
    assert data["invigilator_workload"] == []
    assert data["sessions_by_day"] == []


def test_late_count_today_only_counts_late(
    client: APIClient, officer_user, grant_permission, period, session,
    checkin,
) -> None:
    """One on-time + one late → late_count_today == 1, checkins_today == 2.

    The on-time check-in is the autoloaded ``checkin`` fixture. We add
    a late one for a *different* user so the (session, user, kind)
    unique constraint lets both rows coexist.
    """
    from apps.accounts.models import Role, UserRole
    grant_permission(officer_user, "analytics.view")
    role, _ = Role.objects.update_or_create(
        code="INVIGILATOR", defaults={"name": "Invigilator", "is_active": True}
    )
    other = User.objects.create_user(
        email="late-tester@x.com", full_name="Late Tester",
        password="S3cur3Passw0rd!", is_email_verified=True,
    )
    UserRole.objects.create(user=other, role=role)
    CheckIn.objects.create(
        session=session, user=other, kind="invigilator",
        method="self", recorded_by=other, late=True,
    )
    client.force_authenticate(officer_user)
    data = client.get(reverse("analytics:analytics-summary")).json()
    assert data["checkins_today"] == 2
    assert data["late_count_today"] == 1


def test_attendance_trend_has_12_weeks(
    client: APIClient, officer_user, grant_permission, period, session,
    verified_user,
) -> None:
    """Trend returns 12 buckets, oldest first, latest is the current week."""
    grant_permission(officer_user, "analytics.view")
    CheckIn.objects.create(
        session=session, user=verified_user, kind="invigilator",
        method="self", recorded_by=verified_user, late=False,
    )
    client.force_authenticate(officer_user)
    data = client.get(reverse("analytics:analytics-summary")).json()
    trend = data["attendance_trend"]
    assert len(trend) == 12
    # Each bucket's week_start is a parseable ISO date.
    from datetime import date as _date
    for bucket in trend:
        _date.fromisoformat(bucket["week_start"])  # raises if malformed
        assert isinstance(bucket["count"], int)
    # Latest bucket is the current ISO week (Monday of this week).
    today = timezone.now().date()
    expected_latest = (today - timedelta(days=today.weekday())).isoformat()
    assert trend[-1]["week_start"] == expected_latest


def test_sessions_by_day_capped_at_7(
    client: APIClient, officer_user, grant_permission, period,
    session, second_session, far_session,
) -> None:
    """3 sessions in the active period, one is 10 days out → 7 buckets,
    the day-1 bucket has 2 sessions (the two close ones), the day-10
    session is excluded."""
    grant_permission(officer_user, "analytics.view")
    client.force_authenticate(officer_user)
    data = client.get(reverse("analytics:analytics-summary")).json()
    by_day = data["sessions_by_day"]
    assert len(by_day) == 7
    total_close = sum(b["count"] for b in by_day)
    assert total_close == 2  # session + second_session, but not far_session
    # First day (today + 1d) has both close sessions
    assert by_day[1]["count"] == 2
    # Last day in window (today + 6d) has 0
    assert by_day[6]["count"] == 0
