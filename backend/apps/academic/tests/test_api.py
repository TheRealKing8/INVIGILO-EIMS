"""Tests for the academic CRUD endpoints.

Covers: round-trip CRUD, RBAC, pagination, filter.
"""
from __future__ import annotations

import uuid

import pytest
from django.urls import reverse
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


def test_unauthenticated_returns_401(client: APIClient) -> None:
    response = client.get(reverse("academic:faculty-list"))
    assert response.status_code == 401


def test_authenticated_without_permission_returns_403(
    client: APIClient, verified_user, grant_permission
) -> None:
    # verified_user has no role at all -> 403.
    client.force_authenticate(verified_user)
    response = client.get(reverse("academic:faculty-list"))
    assert response.status_code == 403


def test_faculty_round_trip(client: APIClient, verified_user, grant_permission) -> None:
    grant_permission(verified_user, "academic.faculty.crud")
    client.force_authenticate(verified_user)

    # Use a unique code so the seed data (SAST) doesn't trip the count assertion.
    create = client.post(
        reverse("academic:faculty-list"),
        {"code": "RTT-1", "name": "Round-Trip Faculty"},
        format="json",
    )
    assert create.status_code == 201, create.json()
    faculty_id = create.json()["id"]

    list_ = client.get(reverse("academic:faculty-list"), {"code": "RTT-1"})
    assert list_.status_code == 200
    assert list_.json()["count"] == 1
    assert list_.json()["results"][0]["code"] == "RTT-1"

    detail = client.get(reverse("academic:faculty-detail", args=[faculty_id]))
    assert detail.status_code == 200
    assert detail.json()["name"] == "Round-Trip Faculty"

    patch = client.patch(
        reverse("academic:faculty-detail", args=[faculty_id]),
        {"name": "Renamed Faculty"},
        format="json",
    )
    assert patch.status_code == 200
    assert patch.json()["name"] == "Renamed Faculty"

    delete = client.delete(reverse("academic:faculty-detail", args=[faculty_id]))
    assert delete.status_code == 204
    assert client.get(reverse("academic:faculty-detail", args=[faculty_id])).status_code == 404


def test_department_filtered_by_faculty(client: APIClient, verified_user, grant_permission) -> None:
    grant_permission(verified_user, "academic.faculty.crud", "academic.department.crud")
    client.force_authenticate(verified_user)

    a = client.post(
        reverse("academic:faculty-list"),
        {"code": "AAA", "name": "Faculty A"},
        format="json",
    ).json()
    b = client.post(
        reverse("academic:faculty-list"),
        {"code": "BBB", "name": "Faculty B"},
        format="json",
    ).json()

    client.post(
        reverse("academic:department-list"),
        {"faculty": a["id"], "code": "A1", "name": "Dept A1"},
        format="json",
    )
    client.post(
        reverse("academic:department-list"),
        {"faculty": b["id"], "code": "B1", "name": "Dept B1"},
        format="json",
    )

    filtered = client.get(reverse("academic:department-list"), {"faculty": a["id"]})
    assert filtered.status_code == 200
    codes = [d["code"] for d in filtered.json()["results"]]
    assert codes == ["A1"]


def test_pagination_envelope(client: APIClient, verified_user, grant_permission) -> None:
    grant_permission(verified_user, "academic.faculty.crud")
    client.force_authenticate(verified_user)
    # Snapshot the total before we add ours.
    before = client.get(reverse("academic:faculty-list")).json()["count"]
    for i in range(3):
        client.post(
            reverse("academic:faculty-list"),
            {"code": f"PAG-{i}-{uuid.uuid4().hex[:6]}", "name": f"Faculty {i}"},
            format="json",
        )
    response = client.get(reverse("academic:faculty-list"))
    body = response.json()
    assert body["count"] == before + 3
    assert body["page"] == 1
    assert body["page_size"] == 25
    assert "results" in body


# ---------------------------------------------------------------------------
# Module 2 — University / Campus / CourseUnit endpoints
# ---------------------------------------------------------------------------


def test_university_crud_round_trip(
    client: APIClient, verified_user, grant_permission
) -> None:
    grant_permission(verified_user, "academic.university.crud")
    client.force_authenticate(verified_user)

    create = client.post(
        reverse("academic:university-list"),
        {"code": "UNI-A", "name": "University A"},
        format="json",
    )
    assert create.status_code == 201, create.json()
    uni_id = create.json()["id"]

    detail = client.get(reverse("academic:university-detail", args=[uni_id]))
    assert detail.status_code == 200
    assert detail.json()["code"] == "UNI-A"

    patch = client.patch(
        reverse("academic:university-detail", args=[uni_id]),
        {"name": "University A Renamed"},
        format="json",
    )
    assert patch.status_code == 200
    assert patch.json()["name"] == "University A Renamed"

    delete = client.delete(reverse("academic:university-detail", args=[uni_id]))
    assert delete.status_code == 204


def test_campus_crud_round_trip(
    client: APIClient, verified_user, grant_permission
) -> None:
    grant_permission(verified_user, "academic.university.crud", "academic.campus.crud")
    client.force_authenticate(verified_user)

    uni = client.post(
        reverse("academic:university-list"),
        {"code": "UNI-C", "name": "University C"},
        format="json",
    ).json()

    create = client.post(
        reverse("academic:campus-list"),
        {
            "university": uni["id"],
            "code": "NORTH",
            "name": "North Campus",
            "address": "1 North Way",
        },
        format="json",
    )
    assert create.status_code == 201, create.json()
    campus_id = create.json()["id"]

    detail = client.get(reverse("academic:campus-detail", args=[campus_id]))
    assert detail.status_code == 200
    assert detail.json()["university_code"] == "UNI-C"


def test_campus_unique_per_university(
    client: APIClient, verified_user, grant_permission
) -> None:
    grant_permission(verified_user, "academic.university.crud", "academic.campus.crud")
    client.force_authenticate(verified_user)

    uni = client.post(
        reverse("academic:university-list"),
        {"code": "UNI-D", "name": "University D"},
        format="json",
    ).json()

    first = client.post(
        reverse("academic:campus-list"),
        {"university": uni["id"], "code": "EAST", "name": "East Campus"},
        format="json",
    )
    assert first.status_code == 201, first.json()

    dup = client.post(
        reverse("academic:campus-list"),
        {"university": uni["id"], "code": "EAST", "name": "East Campus (dup)"},
        format="json",
    )
    assert dup.status_code == 400


def test_faculty_can_link_to_campus(
    client: APIClient, verified_user, grant_permission
) -> None:
    grant_permission(
        verified_user,
        "academic.university.crud",
        "academic.campus.crud",
        "academic.faculty.crud",
    )
    client.force_authenticate(verified_user)

    uni = client.post(
        reverse("academic:university-list"),
        {"code": "UNI-E", "name": "University E"},
        format="json",
    ).json()
    campus = client.post(
        reverse("academic:campus-list"),
        {"university": uni["id"], "code": "SOUTH", "name": "South Campus"},
        format="json",
    ).json()
    faculty = client.post(
        reverse("academic:faculty-list"),
        {
            "code": "FCT-E",
            "name": "Faculty E",
            "campus": campus["id"],
        },
        format="json",
    )
    assert faculty.status_code == 201, faculty.json()
    detail = client.get(reverse("academic:faculty-detail", args=[faculty.json()["id"]]))
    assert detail.json()["campus_code"] == "SOUTH"


def test_course_unit_crud_round_trip(
    client: APIClient, verified_user, grant_permission
) -> None:
    grant_permission(
        verified_user,
        "academic.faculty.crud",
        "academic.department.crud",
        "academic.programme.crud",
        "academic.course.crud",
        "academic.unit.crud",
    )
    client.force_authenticate(verified_user)

    # Borrow the seeded faculty / department / program / course chain.
    faculty = client.post(
        reverse("academic:faculty-list"),
        {"code": "UNIT-F", "name": "Faculty F"},
        format="json",
    ).json()
    department = client.post(
        reverse("academic:department-list"),
        {"faculty": faculty["id"], "code": "DPT-U", "name": "Dept U"},
        format="json",
    ).json()
    program = client.post(
        reverse("academic:program-list"),
        {"department": department["id"], "code": "PRG-U", "name": "Program U"},
        format="json",
    ).json()
    course = client.post(
        reverse("academic:course-list"),
        {
            "program": program["id"],
            "code": "CSE-U1",
            "title": "Course U1",
            "credit_hours": 3,
        },
        format="json",
    ).json()

    create = client.post(
        reverse("academic:courseunit-list"),
        {
            "course": course["id"],
            "code": "CSE-U1-A",
            "title": "Course U1 — Section A",
            "credit_hours": 3,
            "year": 1,
            "semester": 1,
        },
        format="json",
    )
    assert create.status_code == 201, create.json()
    unit_id = create.json()["id"]

    detail = client.get(reverse("academic:courseunit-detail", args=[unit_id]))
    assert detail.status_code == 200
    assert detail.json()["course_code"] == "CSE-U1"
    assert detail.json()["year"] == 1
    assert detail.json()["semester"] == 1


def test_course_unit_unique_per_course(
    client: APIClient, verified_user, grant_permission
) -> None:
    grant_permission(
        verified_user,
        "academic.faculty.crud",
        "academic.department.crud",
        "academic.programme.crud",
        "academic.course.crud",
        "academic.unit.crud",
    )
    client.force_authenticate(verified_user)

    faculty = client.post(
        reverse("academic:faculty-list"),
        {"code": "UNIT-G", "name": "Faculty G"},
        format="json",
    ).json()
    department = client.post(
        reverse("academic:department-list"),
        {"faculty": faculty["id"], "code": "DPT-V", "name": "Dept V"},
        format="json",
    ).json()
    program = client.post(
        reverse("academic:program-list"),
        {"department": department["id"], "code": "PRG-V", "name": "Program V"},
        format="json",
    ).json()
    course = client.post(
        reverse("academic:course-list"),
        {
            "program": program["id"],
            "code": "CSE-V1",
            "title": "Course V1",
            "credit_hours": 3,
        },
        format="json",
    ).json()

    first = client.post(
        reverse("academic:courseunit-list"),
        {
            "course": course["id"],
            "code": "CSE-V1-A",
            "title": "V1-A",
            "credit_hours": 3,
            "year": 1,
            "semester": 1,
        },
        format="json",
    )
    assert first.status_code == 201, first.json()

    dup = client.post(
        reverse("academic:courseunit-list"),
        {
            "course": course["id"],
            "code": "CSE-V1-A",
            "title": "V1-A (dup)",
            "credit_hours": 3,
            "year": 1,
            "semester": 1,
        },
        format="json",
    )
    assert dup.status_code == 400


def test_course_unit_filtered_by_year_semester(
    client: APIClient, verified_user, grant_permission
) -> None:
    grant_permission(
        verified_user,
        "academic.faculty.crud",
        "academic.department.crud",
        "academic.programme.crud",
        "academic.course.crud",
        "academic.unit.crud",
    )
    client.force_authenticate(verified_user)

    faculty = client.post(
        reverse("academic:faculty-list"),
        {"code": "UNIT-H", "name": "Faculty H"},
        format="json",
    ).json()
    department = client.post(
        reverse("academic:department-list"),
        {"faculty": faculty["id"], "code": "DPT-W", "name": "Dept W"},
        format="json",
    ).json()
    program = client.post(
        reverse("academic:program-list"),
        {"department": department["id"], "code": "PRG-W", "name": "Program W"},
        format="json",
    ).json()
    course = client.post(
        reverse("academic:course-list"),
        {
            "program": program["id"],
            "code": "CSE-W1",
            "title": "Course W1",
            "credit_hours": 3,
        },
        format="json",
    ).json()
    for code, year, semester in (
        ("CSE-W1-A", 1, 1),
        ("CSE-W1-B", 1, 2),
        ("CSE-W1-C", 2, 1),
    ):
        client.post(
            reverse("academic:courseunit-list"),
            {
                "course": course["id"],
                "code": code,
                "title": code,
                "credit_hours": 3,
                "year": year,
                "semester": semester,
            },
            format="json",
        )

    y1s1 = client.get(
        reverse("academic:courseunit-list"),
        {"year": 1, "semester": 1},
    )
    assert y1s1.status_code == 200
    codes = [u["code"] for u in y1s1.json()["results"]]
    assert "CSE-W1-A" in codes
    assert "CSE-W1-B" not in codes
    assert "CSE-W1-C" not in codes


def test_campus_endpoint_requires_campus_permission(
    client: APIClient, verified_user, grant_permission
) -> None:
    # Only university permission — campus should still 403.
    grant_permission(verified_user, "academic.university.crud")
    client.force_authenticate(verified_user)
    response = client.get(reverse("academic:campus-list"))
    assert response.status_code == 403
