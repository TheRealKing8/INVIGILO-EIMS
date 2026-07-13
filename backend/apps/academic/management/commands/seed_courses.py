"""Seed 12 realistic university courses + their CourseUnit leaves.

Idempotent: every entity is created with ``get_or_create`` keyed on
the natural unique constraint, so re-running the command is a safe
no-op. Use ``--reset`` to wipe and recreate the seeded courses.

Run with::

    python manage.py seed_courses

Why a management command and not a data migration? The full academic
hierarchy is already seeded by ``0002_seed.py`` and
``0004_seed_university_campus_units.py``. This command extends that
data without locking it into a migration; the user can re-run it at
any time to bring a freshly-cloned dev DB up to the latest sample
state.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.academic.models import (
    Campus,
    Course,
    CourseUnit,
    Department,
    Faculty,
    Program,
    University,
)


# (course_code, title, faculty_code, department_code, program_code,
#  program_name, program_duration, credits, year, semester)
SEED: list[tuple[str, str, str, str, str, str, int, int, int, int]] = [
    # CS — BSC-CS already exists, add to it
    ("CS101", "Introduction to Programming",         "SAST", "CS",  "BSC-CS",  "BSc. Computer Science",      4, 3, 1, 1),
    ("CS102", "Computer Organisation & Architecture","SAST", "CS",  "BSC-CS",  "BSc. Computer Science",      4, 3, 1, 2),
    ("CS201", "Data Structures & Algorithms",        "SAST", "CS",  "BSC-CS",  "BSc. Computer Science",      4, 3, 2, 1),
    ("CS202", "Operating Systems",                   "SAST", "CS",  "BSC-CS",  "BSc. Computer Science",      4, 3, 2, 2),
    ("CS301", "Database Systems",                    "SAST", "CS",  "BSC-CS",  "BSc. Computer Science",      4, 3, 3, 1),
    ("CS302", "Software Engineering",                "SAST", "CS",  "BSC-CS",  "BSc. Computer Science",      4, 3, 3, 2),
    # MTH — new program under MTH department
    ("MTH101", "Calculus I",                         "SAST", "MTH", "BSC-MTH", "BSc. Mathematics",            4, 4, 1, 1),
    ("MTH102", "Calculus II",                        "SAST", "MTH", "BSC-MTH", "BSc. Mathematics",            4, 4, 1, 2),
    ("MTH201", "Linear Algebra",                     "SAST", "MTH", "BSC-MTH", "BSc. Mathematics",            4, 3, 2, 1),
    # PHY — new program under PHY department
    ("PHY101", "Mechanics",                          "SAST", "PHY", "BSC-PHY", "BSc. Physics",               4, 3, 1, 1),
    ("PHY201", "Electricity & Magnetism",            "SAST", "PHY", "BSC-PHY", "BSc. Physics",               4, 3, 2, 1),
    # Statistics — STA dept
    ("STA201", "Probability & Statistics",           "SAST", "STA", "BSC-STA", "BSc. Statistics",            4, 3, 2, 1),
]


class Command(BaseCommand):
    help = "Idempotently seed 12 realistic university courses + their CourseUnit leaves."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Hard-delete the seeded courses + their units first (re-runnable from a clean slate).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            self._reset()

        # The top of the hierarchy is seeded by 0004_seed_university_campus_units.py
        # but we re-resolve it here so the command is self-contained for a freshly
        # cloned dev DB.
        university, _ = University.objects.get_or_create(
            code="INV",
            defaults={"name": "Invigilo State University"},
        )
        campus, _ = Campus.objects.get_or_create(
            university=university,
            code="MAIN",
            defaults={"name": "Main Campus", "address": "University Way"},
        )
        faculty, _ = Faculty.objects.get_or_create(
            code="SAST",
            defaults={"name": "Science, Applied Sciences & Technology", "campus": campus},
        )

        # Make sure all the departments we need exist (CS + MTH + PHY exist;
        # STA is new). Idempotent.
        for dcode, dname in (
            ("CS",  "Computer Science"),
            ("MTH", "Mathematics"),
            ("PHY", "Physics"),
            ("STA", "Statistics"),
        ):
            Department.objects.get_or_create(
                faculty=faculty,
                code=dcode,
                defaults={"name": dname},
            )

        n_courses_created = 0
        n_courses_existing = 0
        n_units = 0
        n_programs = 0
        for (
            ccode, ctitle, _fcode, dcode, pcode, pname, pdur,
            credits, year, semester,
        ) in SEED:
            dept = Department.objects.get(faculty=faculty, code=dcode)
            program, created = Program.objects.get_or_create(
                department=dept,
                code=pcode,
                defaults={"name": pname, "duration_years": pdur},
            )
            if created:
                n_programs += 1

            # Course.code is globally unique, so we look it up by code
            # alone. If a legacy course already exists (the 0002_seed
            # migration put MTH101/PHY101 under BSC-CS for historic
            # reasons) we leave it alone — re-parenting is out of scope
            # for this command.
            course, created = Course.objects.get_or_create(
                code=ccode,
                defaults={
                    "program": program,
                    "title": ctitle,
                    "credit_hours": credits,
                },
            )
            if created:
                n_courses_created += 1
            else:
                n_courses_existing += 1

            # CourseUnit code = "<COURSE_CODE>-Y<Y>S<S>" so the unit
            # code is unique within a course (enforced by the model).
            unit_code = f"{ccode}-Y{year}S{semester}"
            _, unit_created = CourseUnit.objects.get_or_create(
                course=course,
                code=unit_code,
                defaults={
                    "title": f"{ctitle} — Y{year}S{semester}",
                    "credit_hours": credits,
                    "year": year,
                    "semester": semester,
                },
            )
            if unit_created:
                n_units += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: {n_courses_created} new + {n_courses_existing} existing courses, "
                f"{n_units} new course units, {n_programs} new programs."
            )
        )

    def _reset(self) -> None:
        # Only wipe the courses this command owns. Other courses in the
        # database (the 4 legacy ones from 0002_seed.py) are left alone.
        target_codes = [row[0] for row in SEED]
        units_deleted, _ = CourseUnit.objects.filter(
            course__code__in=target_codes
        ).delete()
        courses_deleted, _ = Course.objects.filter(code__in=target_codes).delete()
        self.stdout.write(
            self.style.WARNING(
                f"--reset: deleted {courses_deleted} courses, {units_deleted} course units."
            )
        )
