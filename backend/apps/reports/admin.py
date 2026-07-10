from django.contrib import admin

from .models import ReportExport


@admin.register(ReportExport)
class ReportExportAdmin(admin.ModelAdmin):
    list_display = ("title", "format", "audience", "cycle", "generated_by", "generated_at")
    list_filter = ("format", "audience", "cycle")
    search_fields = ("title",)
    date_hierarchy = "generated_at"
