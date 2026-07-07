"""Test settings — used by pytest-django.

Key differences from dev:
    * SQLite in-memory database (no external Postgres needed for tests).
    * Faster password hasher (MD5 — never use in production).
    * In-memory email backend.
    * Hash-based (locmem) cache.
    * No Celery — tasks run synchronously via CELERY_TASK_ALWAYS_EAGER.
"""
from __future__ import annotations

from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Run Celery tasks synchronously in tests.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Disable throttling in tests so we don't have to dance with anon/user IDs.
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # type: ignore[name-defined]  # noqa: F405
    "DEFAULT_THROTTLE_CLASSES": (),
    "DEFAULT_THROTTLE_RATES": {},
}
