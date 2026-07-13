"""Add the ``LoginOTP`` model for the admin second-factor step.

Each row is one issued code: ``otp_token`` is the public lookup key
returned to the client, ``code_hash`` is the argon2id hash of the
6-digit code the user types in. ``consumed_at`` is set on success or
once the per-row attempt counter is exhausted. After five failed
attempts the row is revoked, mirroring the failed-login lockout
policy but scoped to a single OTP challenge.
"""
from __future__ import annotations

import uuid

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_seed_exam_session_create_view"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoginOTP",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="login_otps",
                        to="accounts.user",
                    ),
                ),
                (
                    "otp_token",
                    models.CharField(db_index=True, max_length=64, unique=True),
                ),
                ("code_hash", models.CharField(max_length=255)),
                ("expires_at", models.DateTimeField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
