"""Academic structure.

The full hierarchy is::

    University → Campus → Faculty → Department → Program → Course → CourseUnit

Exam sessions reference a ``CourseUnit`` (the leaf node — one course
unit, one exam sitting). Row-level access scoping keys off
``Department.faculty`` and ``Faculty.campus`` in
``apps.core.scopes``.

Legacy deployments may not have a Campus on every Faculty — the FK is
nullable so existing rows keep working after the migration.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class University(BaseModel):
    """Top of the academic hierarchy. A single institution may have
    multiple campuses; the system is multi-university capable but in
    practice most installations run a single university.
    """
    code = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    vice_chancellor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="universities_led",
    )

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code} — {self.name}"


class Campus(BaseModel):
    """A physical site belonging to a university. Faculties hang off a
    campus so a multi-campus university can run faculties per location
    (e.g. a Main campus and a Medical campus).
    """
    university = models.ForeignKey(
        University, on_delete=models.PROTECT, related_name="campuses"
    )
    code = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("university", "code"),
                name="academic_campus_uniq_per_uni",
            ),
        ]
        indexes = [models.Index(fields=("university", "code"), name="academic_campus_uni_code_idx")]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.university.code}/{self.code} — {self.name}"


class Faculty(BaseModel):
    campus = models.ForeignKey(
        Campus,
        on_delete=models.PROTECT,
        related_name="faculties",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    dean = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="faculties_led",
    )

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code} — {self.name}"


class Department(BaseModel):
    faculty = models.ForeignKey(
        Faculty, on_delete=models.PROTECT, related_name="departments"
    )
    code = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    head = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departments_led",
    )

    class Meta:
        ordering = ("code",)
        indexes = [models.Index(fields=("faculty", "code"))]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code} — {self.name}"


class Program(BaseModel):
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="programs"
    )
    code = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    duration_years = models.PositiveSmallIntegerField(default=4)

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code} — {self.name}"


class Course(BaseModel):
    program = models.ForeignKey(
        Program, on_delete=models.PROTECT, related_name="courses"
    )
    code = models.CharField(max_length=32, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    credit_hours = models.PositiveSmallIntegerField(default=3)

    class Meta:
        ordering = ("code",)
        indexes = [models.Index(fields=("program", "code"))]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code} — {self.title}"


class CourseUnit(BaseModel):
    """A specific offering of a Course in a given academic year +
    semester. This is the leaf node that examinations hang off — one
    CourseUnit, one ExamSession. We split it from ``Course`` so that
    the same course code (e.g. ``CS101``) can be offered to multiple
    programmes / semesters without duplicating the parent Course.
    """
    course = models.ForeignKey(
        Course, on_delete=models.PROTECT, related_name="units"
    )
    code = models.CharField(max_length=32, db_index=True)
    title = models.CharField(max_length=255)
    credit_hours = models.PositiveSmallIntegerField(default=3)
    year = models.PositiveSmallIntegerField()
    semester = models.PositiveSmallIntegerField()  # 1 or 2

    class Meta:
        ordering = ("course__code", "year", "semester", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("course", "code"),
                name="academic_unit_uniq_per_course",
            ),
        ]
        indexes = [models.Index(fields=("course", "year", "semester"), name="academic_courseunit_cyr_idx")]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code} (Y{self.year}S{self.semester}) — {self.title}"


__all__ = [
    "Campus",
    "Course",
    "CourseUnit",
    "Department",
    "Faculty",
    "Program",
    "University",
]
