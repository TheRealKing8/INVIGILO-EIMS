from rest_framework import serializers

from .models import Allocation, AllocationRun, Conflict


class AllocationRunSerializer(serializers.ModelSerializer):
    triggered_by_email = serializers.CharField(
        source="triggered_by.email", read_only=True, default=None
    )
    period_code = serializers.CharField(source="period.code", read_only=True)

    class Meta:
        model = AllocationRun
        fields = (
            "id",
            "period",
            "period_code",
            "triggered_by",
            "triggered_by_email",
            "sessions_total",
            "sessions_placed",
            "avg_workload",
            "max_workload",
            "capacity_utilisation",
            "runtime_seconds",
            "finished_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "period_code",
            "triggered_by_email",
        )


class AllocationSerializer(serializers.ModelSerializer):
    exam_code = serializers.CharField(source="session.course.code", read_only=True)
    exam_title = serializers.CharField(source="session.course.title", read_only=True)
    invigilator_name = serializers.CharField(source="invigilator.user.full_name", read_only=True)
    invigilator_department = serializers.CharField(
        source="invigilator.primary_department.code", read_only=True, default=None
    )
    room_code = serializers.CharField(source="room.code", read_only=True, default=None)
    building_code = serializers.CharField(source="room.building.code", read_only=True, default=None)
    session_starts_at = serializers.DateTimeField(source="session.starts_at", read_only=True)
    session_ends_at = serializers.DateTimeField(source="session.ends_at", read_only=True)

    class Meta:
        model = Allocation
        fields = (
            "id",
            "run",
            "session",
            "exam_code",
            "exam_title",
            "session_starts_at",
            "session_ends_at",
            "invigilator",
            "invigilator_name",
            "invigilator_department",
            "room",
            "room_code",
            "building_code",
            "role",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "exam_code",
            "exam_title",
            "session_starts_at",
            "session_ends_at",
            "invigilator_name",
            "invigilator_department",
            "room_code",
            "building_code",
        )


class ConflictSerializer(serializers.ModelSerializer):
    session_code = serializers.CharField(source="session.course.code", read_only=True, default=None)
    invigilator_name = serializers.CharField(
        source="invigilator.user.full_name", read_only=True, default=None
    )

    class Meta:
        model = Conflict
        fields = (
            "id",
            "run",
            "session",
            "session_code",
            "invigilator",
            "invigilator_name",
            "type",
            "severity",
            "detail",
            "created_at",
        )
        read_only_fields = ("id", "created_at", "session_code", "invigilator_name")
