from django.contrib import admin

from .models import Building, Room


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("code", "building", "capacity", "is_active")
    list_filter = ("is_active", "building")
    search_fields = ("code", "name")
