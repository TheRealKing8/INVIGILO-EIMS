from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "target_type", "target_id", "request_id")
    list_filter = ("action", "target_type")
    search_fields = ("target_id", "action", "actor__email")
    date_hierarchy = "created_at"
    readonly_fields = tuple(
        f.name for f in AuditLog._meta.fields
    )  # audit logs are append-only
