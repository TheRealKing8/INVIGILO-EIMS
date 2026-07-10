from django.contrib import admin

from .models import Incident


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "session", "severity", "status", "reporter", "reported_at")
    list_filter = ("severity", "status", "reported_at")
    search_fields = ("title", "body", "session__course__code")
    date_hierarchy = "reported_at"
    raw_id_fields = ("session", "reporter")
