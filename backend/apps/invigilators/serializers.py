from rest_framework import serializers

from .models import Availability, InvigilatorProfile


class InvigilatorProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    primary_department_code = serializers.CharField(
        source="primary_department.code", read_only=True, default=None
    )
    primary_department_name = serializers.CharField(
        source="primary_department.name", read_only=True, default=None
    )

    class Meta:
        model = InvigilatorProfile
        fields = (
            "id",
            "user",
            "email",
            "full_name",
            "primary_department",
            "primary_department_code",
            "primary_department_name",
            "max_sessions_per_cycle",
            "rating",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "email",
            "full_name",
            "primary_department_code",
            "primary_department_name",
        )


class AvailabilitySerializer(serializers.ModelSerializer):
    invigilator_email = serializers.CharField(source="invigilator.user.email", read_only=True)
    invigilator_name = serializers.CharField(source="invigilator.user.full_name", read_only=True)

    class Meta:
        model = Availability
        fields = (
            "id",
            "invigilator",
            "invigilator_email",
            "invigilator_name",
            "date",
            "status",
            "note",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "invigilator_email",
            "invigilator_name",
        )
