"""Django admin for notifications.

Read-only browsing — operators want to see "did the user actually get
the email" without writing to the table. A write here would break the
``is_read`` / ``read_at`` invariants the views maintain.
"""
from __future__ import annotations

from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "created_at",
        "recipient",
        "kind",
        "title",
        "is_read",
        "email_sent_at",
        "email_failed",
    )
    list_filter = ("kind", "is_read", "email_failed")
    search_fields = (
        "recipient__email",
        "recipient__full_name",
        "title",
        "body",
    )
    date_hierarchy = "created_at"
    readonly_fields = (
        "created_at",
        "updated_at",
        "is_read",
        "read_at",
        "email_sent_at",
        "email_failed",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request):  # type: ignore[no-untyped-def]
        return False


__all__ = ["NotificationAdmin"]
