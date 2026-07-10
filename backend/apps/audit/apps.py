from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit"
    label = "audit"
    verbose_name = "Audit log"

    def ready(self) -> None:  # pragma: no cover
        # Signals are wired in Phase 5 alongside the test suite.
        return
