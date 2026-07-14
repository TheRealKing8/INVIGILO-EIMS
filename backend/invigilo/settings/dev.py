"""Local development settings."""
from __future__ import annotations

from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Console email is fine for development.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# CORS is wide open locally.
CORS_ALLOW_ALL_ORIGINS = True

# Pretty logging on stdout.
LOGGING["handlers"]["console"]["formatter"] = "console"  # noqa: F405

# In-memory channel layer — we don't run a real broker locally unless the
# docker-compose stack is up. Phase 2 doesn't use channels yet.
CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}  # type: ignore[misc]

# Use an in-memory cache locally so the throttling and session layers do not
# depend on Redis being available.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "invigilo-local",
    }
}

# ----------------------------------------------------------------------------
# Celery — run tasks synchronously in dev.
# ----------------------------------------------------------------------------
# Without this, ``send_login_otp_email.delay(...)`` queues the email to
# Redis and a Celery worker has to pick it up. In a local dev session
# (no worker running) the OTP email never gets sent, the admin can't
# sign in, and the console gives no hint that anything is broken.
#
# ``CELERY_TASK_ALWAYS_EAGER=True`` runs the task in-process, so the
# email prints to the dev console (via the console backend above) the
# moment the login endpoint returns. ``CELERY_TASK_EAGER_PROPAGATES``
# makes exceptions raised inside the task surface as 500s — handy in
# dev, painful in prod (where you want the broker to retry).
# ----------------------------------------------------------------------------
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
