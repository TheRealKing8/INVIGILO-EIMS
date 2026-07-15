"""Django app config for the analytics app."""
from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    name = "apps.analytics"
    label = "analytics"
    default_auto_field = "django.db.models.BigAutoField"


__all__ = ["AnalyticsConfig"]
