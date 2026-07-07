"""Filter sets for the accounts app.

The accounts app keeps its filter logic in the model managers (the
``User.all_objects`` hard manager and the soft-delete aware
``User.objects``) so this file is a placeholder for future search
filters (e.g. a free-text filter that joins ``User.email``,
``User.full_name`` and ``UserRole.role.name``).
"""
from __future__ import annotations
