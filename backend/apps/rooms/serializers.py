from rest_framework import serializers

from .models import Building, Room


class BuildingSerializer(serializers.ModelSerializer):
    room_count = serializers.IntegerField(source="rooms.count", read_only=True)

    class Meta:
        model = Building
        fields = (
            "id",
            "code",
            "name",
            "address",
            "room_count",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "room_count")


class RoomSerializer(serializers.ModelSerializer):
    building_code = serializers.CharField(source="building.code", read_only=True)
    building_name = serializers.CharField(source="building.name", read_only=True)

    class Meta:
        model = Room
        fields = (
            "id",
            "building",
            "building_code",
            "building_name",
            "code",
            "name",
            "capacity",
            "equipment",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "building_code",
            "building_name",
        )
