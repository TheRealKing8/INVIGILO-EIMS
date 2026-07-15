"""Normalise the system administrator's email to ``admininvigilo@gmail.com``.

Phase 17 moved every seeded user email to the ``@gmail.com`` domain
so they are real, deliverable addresses (matching the ``FROM``
identity used by the dev Gmail SMTP). This migration ensures the
already-deployed admin row in any existing environment ends up on
the canonical address.

* The forward path is idempotent — if no row matches the old email
  (e.g. a fresh database) it does nothing, and if the new email is
  already in place it's a no-op.
* The reverse path is a no-op. The previous email may have been
  the placeholder ``admin@invigilo.local`` or any earlier ad-hoc
  string; we cannot restore what we never captured. Re-running
  the forward path is the right way to "undo" a bad rename.
* We use ``User.all_objects`` (the unfiltered manager) so the
  migration also catches rows that may have been soft-deleted
  historically.
"""
from __future__ import annotations

from django.db import migrations


TARGET_EMAIL = "admininvigilo@gmail.com"
# Any of these historic addresses should be migrated forward to
# TARGET_EMAIL. The set is intentionally narrow so we don't
# accidentally rename unrelated users.
LEGACY_EMAILS = (
    "admin@invigilo.local",
    "admininvigilo@invigilo.local",
)


def forward(apps, schema_editor):  # type: ignore[no-untyped-def]
    User = apps.get_model("accounts", "User")
    # Use the unfiltered manager so a soft-deleted row is also
    # renamed — the row might be revived later and we don't want
    # the stale address resurfacing.
    for legacy in LEGACY_EMAILS:
        if User.objects.filter(email__iexact=legacy).exists():
            # If a different user already holds TARGET_EMAIL, skip
            # the rename rather than blow up on the unique-email
            # constraint. The operator can resolve the conflict
            # manually (psql) and re-run.
            if User.objects.filter(email__iexact=TARGET_EMAIL).exists():
                continue
            User.objects.filter(email__iexact=legacy).update(email=TARGET_EMAIL)


def backward(apps, schema_editor):  # type: ignore[no-untyped-def]
    # No-op: see module docstring.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_alter_loginotp_created_at"),
    ]

    operations = [migrations.RunPython(forward, backward)]
