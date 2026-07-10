from django.contrib import admin

from .models import Allocation, AllocationRun, Conflict


@admin.register(AllocationRun)
class AllocationRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "period",
        "triggered_by",
        "sessions_placed",
        "sessions_total",
        "runtime_seconds",
        "created_at",
    )
    list_filter = ("period",)
    date_hierarchy = "created_at"


@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    list_display = ("session", "invigilator", "room", "status", "role", "run")
    list_filter = ("status", "role", "session__period")
    search_fields = ("invigilator__user__email", "invigilator__user__full_name")
    raw_id_fields = ("session", "invigilator", "room", "run")


@admin.register(Conflict)
class ConflictAdmin(admin.ModelAdmin):
    list_display = ("run", "session", "invigilator", "type", "severity")
    list_filter = ("type", "severity")
    search_fields = ("detail",)
    raw_id_fields = ("session", "invigilator", "run")
