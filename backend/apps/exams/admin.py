from django.contrib import admin

from .models import ExamPeriod, ExamSession
from .student_registration import StudentRegistration


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


@admin.register(StudentRegistration)
class StudentRegistrationAdmin(admin.ModelAdmin):
    list_display = ("student", "session", "student_code")
    list_filter = ("session__period", "session__status")
    search_fields = ("student__email", "student__full_name", "student_code")
    raw_id_fields = ("session", "student")
