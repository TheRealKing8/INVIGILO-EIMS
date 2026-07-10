from django.contrib import admin

from .models import Availability, InvigilatorProfile


@admin.register(InvigilatorProfile)
class InvigilatorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "primary_department", "max_sessions_per_cycle", "rating", "is_active")
    list_filter = ("is_active", "primary_department")
    search_fields = ("user__email", "user__full_name")
    raw_id_fields = ("user",)


@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ("invigilator", "date", "status", "note")
    list_filter = ("status", "date")
    search_fields = ("invigilator__user__email",)
    date_hierarchy = "date"
