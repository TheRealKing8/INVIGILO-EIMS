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

# Belt-and-braces: even though DJANGO_SETTINGS_MODULE points here, some
# pytest-django bootstraps cache ROOT_URLCONF from a different settings
# module. Forcing it here makes `reverse(...)` in tests find the real
# URL patterns instead of the bare "no patterns" resolver.
ROOT_URLCONF = "invigilo.urls"

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

# Cookie + session tests run in-process without HTTPS, so we relax the
# ``Secure`` flag (the production default is ``not DEBUG``). We also
# expose the refresh token in the response body so the legacy tests
# that read ``pair["refresh"]`` keep working.
JWT_REFRESH_COOKIE_SECURE = False
JWT_INCLUDE_REFRESH_IN_BODY = True
