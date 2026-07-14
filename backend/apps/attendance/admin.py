from django.contrib import admin

from .models import CheckIn


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "user", "kind", "method", "late", "at")
    list_filter = ("kind", "method", "late", "at")
    search_fields = (
        "user__email",
        "user__full_name",
        "session__course__code",
        "location",
    )
    date_hierarchy = "at"
    raw_id_fields = ("session", "user", "recorded_by")
    readonly_fields = ("created_at", "updated_at", "at")
