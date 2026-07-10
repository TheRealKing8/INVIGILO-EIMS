"""Extend the academic hierarchy to its full form.

Adds three new entities to close the gap in the spec's chain::

    University → Campus → Faculty → Department → Program → Course → CourseUnit

* ``University`` — the top of the hierarchy. A single institution may
  have multiple campuses; the system is multi-university capable.
* ``Campus`` — a physical site belonging to a university. Faculties
  hang off a campus so a multi-campus university can run faculties
  per location.
* ``CourseUnit`` — a specific offering of a ``Course`` in a given
  academic year + semester. This is the leaf node that examinations
  hang off — one CourseUnit, one ExamSession.

Also adds a nullable ``campus`` FK to ``Faculty`` so existing
faculties keep working after the migration.
"""
from __future__ import annotations

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("academic", "0002_seed"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1) Top of the hierarchy
        migrations.CreateModel(
            name="University",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("deactivated_at", models.DateTimeField(blank=True, null=True)),
                ("code", models.CharField(db_index=True, max_length=32, unique=True)),
                ("name", models.CharField(max_length=255)),
                (
                    "vice_chancellor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="universities_led",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("code",)},
        ),
        # 2) Campus belongs to a University
        migrations.CreateModel(
            name="Campus",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("deactivated_at", models.DateTimeField(blank=True, null=True)),
                ("code", models.CharField(db_index=True, max_length=32)),
                ("name", models.CharField(max_length=255)),
                ("address", models.CharField(blank=True, max_length=255)),
                (
                    "university",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="campuses",
                        to="academic.university",
                    ),
                ),
            ],
            options={
                "ordering": ("code",),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("university", "code"),
                        name="academic_campus_uniq_per_uni",
                    ),
                ],
            },
        ),
        migrations.AddIndex(
            model_name="campus",
            index=models.Index(
                fields=("university", "code"),
                name="academic_campus_uni_code_idx",
            ),
        ),
        # 3) Faculty gains a nullable campus FK (legacy data stays valid)
        migrations.AddField(
            model_name="faculty",
            name="campus",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="faculties",
                to="academic.campus",
            ),
        ),
        # 4) Leaf — CourseUnit hangs off a Course
        migrations.CreateModel(
            name="CourseUnit",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("deactivated_at", models.DateTimeField(blank=True, null=True)),
                ("code", models.CharField(db_index=True, max_length=32)),
                ("title", models.CharField(max_length=255)),
                ("credit_hours", models.PositiveSmallIntegerField(default=3)),
                ("year", models.PositiveSmallIntegerField()),
                ("semester", models.PositiveSmallIntegerField()),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="units",
                        to="academic.course",
                    ),
                ),
            ],
            options={
                "ordering": ("course__code", "year", "semester", "code"),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("course", "code"),
                        name="academic_unit_uniq_per_course",
                    ),
                ],
            },
        ),
        migrations.AddIndex(
            model_name="courseunit",
            index=models.Index(
                fields=("course", "year", "semester"),
                name="academic_courseunit_cyr_idx",
            ),
        ),
    ]
