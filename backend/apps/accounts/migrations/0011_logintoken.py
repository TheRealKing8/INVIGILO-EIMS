"""Add the ``LoginToken`` model for the multi-role login step (Phase 21).

Issued by ``POST /auth/login/`` when the authenticated user has more
than one active role. The client returns it to
``POST /auth/select-role/`` alongside the chosen role code; the row is
marked ``consumed_at`` on first use so it can't be replayed.

Not a JWT — we need server-side state for revocation and single-use
enforcement, and JWTs don't give us that without a deny-list. The 5-
minute lifetime matches the time a user might take to read the role
list and click a card.
"""
from __future__ import annotations

import uuid

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_admin_email_to_gmail"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoginToken",
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
                        related_name="login_tokens",
                        to="accounts.user",
                    ),
                ),
                (
                    "token_hash",
                    models.CharField(db_index=True, max_length=128, unique=True),
                ),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
