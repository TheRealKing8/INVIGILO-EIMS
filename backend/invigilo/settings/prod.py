"""Production settings.

Loaded when ``APP_ENV=prod`` (or when ``DJANGO_SETTINGS_MODULE`` points
here directly, which is what the WSGI/ASGI entry points do).

Anything that depends on a real secret in production must be loaded from
the environment; this file contains no secrets of its own.
"""
from __future__ import annotations

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

# Real hosts must be explicit.
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

# TLS / HSTS
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Email defaults to SMTP in production.
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)

# Sentry (optional)
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.05),
        send_default_pii=False,
        environment=env("APP_ENV", default="prod"),
    )

# Use JSON logging in production.
LOGGING["formatters"]["json"] = {  # noqa: F405
    "()": "invigilo.logging.JSONFormatter",
}
LOGGING["handlers"]["console"]["formatter"] = "json"  # noqa: F405
