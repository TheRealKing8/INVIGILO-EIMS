from django.contrib import admin

from .models import (
    Campus,
    Course,
    CourseUnit,
    Department,
    Faculty,
    Program,
    University,
)


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "vice_chancellor", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "university", "address", "is_active")
    list_filter = ("is_active", "university")
    search_fields = ("code", "name")


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "campus", "dean", "is_active")
    list_filter = ("is_active", "campus")
    search_fields = ("code", "name")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "faculty", "head", "is_active")
    list_filter = ("is_active", "faculty")
    search_fields = ("code", "name")


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "department", "duration_years", "is_active")
    list_filter = ("is_active", "department", "duration_years")
    search_fields = ("code", "name")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "program", "credit_hours", "is_active")
    list_filter = ("is_active", "program", "credit_hours")
    search_fields = ("code", "title")


@admin.register(CourseUnit)
class CourseUnitAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "course", "year", "semester", "credit_hours", "is_active")
    list_filter = ("is_active", "course", "year", "semester")
    search_fields = ("code", "title")
