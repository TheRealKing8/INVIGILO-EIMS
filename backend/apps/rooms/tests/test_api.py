"""Tests for the rooms CRUD endpoints."""
from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


def test_building_round_trip(client: APIClient, verified_user, grant_permission) -> None:
    grant_permission(verified_user, "room.crud")
    client.force_authenticate(verified_user)

    create = client.post(
        reverse("rooms:building-list"),
        {"code": "ENG", "name": "Engineering Block", "address": "1 Quad"},
        format="json",
    )
    assert create.status_code == 201, create.json()
    bid = create.json()["id"]

    detail = client.get(reverse("rooms:building-detail", args=[bid]))
    assert detail.status_code == 200
    assert detail.json()["code"] == "ENG"

    patch = client.patch(
        reverse("rooms:building-detail", args=[bid]),
        {"name": "Engineering & Applied Sciences"},
        format="json",
    )
    assert patch.status_code == 200
    assert patch.json()["name"] == "Engineering & Applied Sciences"


def test_room_requires_building(
    client: APIClient, verified_user, grant_permission
) -> None:
    grant_permission(verified_user, "room.crud")
    client.force_authenticate(verified_user)

    response = client.post(
        reverse("rooms:room-list"),
        {"code": "R-1", "capacity": 50, "equipment": ""},
        format="json",
    )
    # Building FK is required.
    assert response.status_code == 400


def test_room_capacity_filter(client: APIClient, verified_user, grant_permission) -> None:
    grant_permission(verified_user, "room.crud")
    client.force_authenticate(verified_user)
    b = client.post(
        reverse("rooms:building-list"),
        {"code": "CAPX", "name": "Capacity Test Block"},
        format="json",
    ).json()
    for cap in (30, 80, 150):
        client.post(
            reverse("rooms:room-list"),
            {"building": b["id"], "code": f"CAPX-{cap}", "capacity": cap, "equipment": ""},
            format="json",
        )
    # django_filters exposes the integer field as exact match by default.
    response = client.get(reverse("rooms:room-list"), {"building": b["id"], "capacity": 80})
    assert response.status_code == 200
    codes = [r["code"] for r in response.json()["results"]]
    assert codes == ["CAPX-80"]


def test_unauthenticated_returns_401(client: APIClient) -> None:
    assert client.get(reverse("rooms:building-list")).status_code == 401
    assert client.get(reverse("rooms:room-list")).status_code == 401
