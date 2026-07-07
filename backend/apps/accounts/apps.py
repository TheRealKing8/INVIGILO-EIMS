"""AppConfig for the accounts app."""
from __future__ import annotations

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "Accounts"

    def ready(self) -> None:
        # Wire the signal handlers that maintain role/permission caches.
        from . import signals  # noqa: F401
