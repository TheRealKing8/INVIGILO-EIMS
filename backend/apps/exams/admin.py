from django.contrib import admin

from .models import ExamPeriod, ExamSession


@admin.register(ExamPeriod)
class ExamPeriodAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "starts_on", "ends_on", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(ExamSession)
class ExamSessionAdmin(admin.ModelAdmin):
    list_display = ("course", "period", "starts_at", "room", "status", "registered", "capacity")
    list_filter = ("status", "period", "room__building")
    search_fields = ("course__code", "course__title")
    date_hierarchy = "starts_at"
