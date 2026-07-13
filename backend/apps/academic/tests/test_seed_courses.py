"""Tests for the seed_courses management command.

The command should be idempotent and produce a known set of courses
anchored to real programs / departments / faculties.
"""
from __future__ import annotations

import pytest
from django.core.management import call_command

from apps.academic.models import Course, CourseUnit, Program


pytestmark = pytest.mark.django_db


EXPECTED_COURSE_CODES = {
    "CS101", "CS102", "CS201", "CS202", "CS301", "CS302",
    "MTH101", "MTH102", "MTH201",
    "PHY101", "PHY201",
    "STA201",
}


def test_seed_courses_creates_all_expected_courses() -> None:
    call_command("seed_courses")
    codes = set(Course.objects.values_list("code", flat=True))
    assert EXPECTED_COURSE_CODES.issubset(codes), (
        f"Missing courses: {EXPECTED_COURSE_CODES - codes}"
    )


def test_seed_courses_creates_course_units() -> None:
    call_command("seed_courses")
    # Every seeded course should have at least one unit attached.
    for code in ("CS101", "MTH101", "PHY201", "STA201"):
        course = Course.objects.get(code=code)
        assert CourseUnit.objects.filter(course=course).exists(), (
            f"Course {code} has no CourseUnit leaves"
        )


def test_seed_courses_creates_programs_per_department() -> None:
    call_command("seed_courses")
    program_codes = set(Program.objects.values_list("code", flat=True))
    for pcode in ("BSC-CS", "BSC-MTH", "BSC-PHY", "BSC-STA"):
        assert pcode in program_codes, f"Missing program {pcode}"


def test_seed_courses_is_idempotent() -> None:
    call_command("seed_courses")
    after_first = Course.objects.count()
    call_command("seed_courses")
    after_second = Course.objects.count()
    assert after_first == after_second


def test_seed_courses_reset_wipes_and_recreates() -> None:
    call_command("seed_courses")
    # Wipe a known course + its units to confirm --reset re-creates it.
    course = Course.objects.get(code="CS102")
    CourseUnit.objects.filter(course=course).delete()
    course.delete()
    assert not Course.objects.filter(code="CS102").exists()
    call_command("seed_courses", "--reset")
    assert Course.objects.filter(code="CS102").exists()
