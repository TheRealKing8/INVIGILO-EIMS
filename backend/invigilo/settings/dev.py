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
