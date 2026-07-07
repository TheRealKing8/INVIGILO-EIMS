"""Settings package — selects the right module via DJANGO_SETTINGS_MODULE.

The default is ``invigilo.settings.dev``; production deployments should set
``DJANGO_SETTINGS_MODULE=invigilo.settings.prod`` and supply all secrets
through the environment.
"""
from __future__ import annotations

import os


def _default_settings_module() -> str:
    env = os.environ.get("APP_ENV", "dev").lower()
    return {
        "prod": "invigilo.settings.prod",
        "production": "invigilo.settings.prod",
        "test": "invigilo.settings.test",
        "testing": "invigilo.settings.test",
    }.get(env, "invigilo.settings.dev")


if "DJANGO_SETTINGS_MODULE" not in os.environ:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", _default_settings_module())
