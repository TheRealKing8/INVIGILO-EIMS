"""Tests for invigilator profiles and per-date availability."""
from __future__ import annotations

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.academic.models import Department, Faculty
from apps.invigilators.models import InvigilatorProfile


User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def department(db) -> Department:  # type: ignore[no-untyped-def]
    f = Faculty.objects.create(code="F", name="F")
    return Department.objects.create(faculty=f, code="D", name="D")


@pytest.fixture
def invigilator_user(db) -> User:  # type: ignore[no-untyped-def]
    return User.objects.create_user(
        email="inv1@x.com", full_name="Inv One", password="S3cur3Passw0rd!"
    )


def test_profile_create_and_list(
    client: APIClient, verified_user, grant_permission, invigilator_user, department
) -> None:
    grant_permission(verified_user, "people.invigilator.crud")
    client.force_authenticate(verified_user)
    response = client.post(
        reverse("invigilators:invigilator-profile-list"),
        {
            "user": invigilator_user.id,
            "primary_department": department.id,
            "max_sessions_per_cycle": 5,
            "rating": "4.75",
        },
        format="json",
    )
    assert response.status_code == 201, response.json()
    assert InvigilatorProfile.objects.filter(user=invigilator_user).exists()

    list_ = client.get(reverse("invigilators:invigilator-profile-list"))
    assert list_.status_code == 200
    assert list_.json()["count"] == 1


def test_availability_unique_per_date(
    client: APIClient, verified_user, grant_permission, invigilator_user, department
) -> None:
    grant_permission(verified_user, "people.invigilator.crud", "people.availability.update_own")
    client.force_authenticate(verified_user)
    profile = InvigilatorProfile.objects.create(
        user=invigilator_user, primary_department=department, max_sessions_per_cycle=4
    )

    payload = {
        "invigilator": profile.id,
        "date": date(2026, 8, 1).isoformat(),
        "status": "leave",
    }
    first = client.post(reverse("invigilators:availability-list"), payload, format="json")
    assert first.status_code == 201, first.json()
    second = client.post(reverse("invigilators:availability-list"), payload, format="json")
    assert second.status_code == 400


def test_availability_filter_by_status(
    client: APIClient, verified_user, grant_permission, invigilator_user, department
) -> None:
    grant_permission(verified_user, "people.invigilator.crud", "people.availability.update_own")
    client.force_authenticate(verified_user)
    profile = InvigilatorProfile.objects.create(
        user=invigilator_user, primary_department=department
    )
    client.post(
        reverse("invigilators:availability-list"),
        {
            "invigilator": profile.id,
            "date": date(2026, 8, 1).isoformat(),
            "status": "leave",
        },
        format="json",
    )
    response = client.get(reverse("invigilators:availability-list"), {"status": "leave"})
    assert response.status_code == 200
    assert response.json()["count"] == 1
