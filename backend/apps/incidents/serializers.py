from rest_framework import serializers

from .models import Incident


class IncidentSerializer(serializers.ModelSerializer):
    session_code = serializers.CharField(source="session.course.code", read_only=True, default=None)
    session_starts_at = serializers.DateTimeField(source="session.starts_at", read_only=True, default=None)
    room_code = serializers.CharField(source="session.room.code", read_only=True, default=None)
    reporter_email = serializers.CharField(source="reporter.email", read_only=True, default=None)
    reporter_name = serializers.CharField(source="reporter.full_name", read_only=True, default=None)
    resolved_by_email = serializers.CharField(source="resolved_by.email", read_only=True, default=None)

    class Meta:
        model = Incident
        fields = (
            "id",
            "title",
            "body",
            "session",
            "session_code",
            "session_starts_at",
            "room_code",
            "reporter",
            "reporter_email",
            "reporter_name",
            "severity",
            "status",
            "reported_at",
            "resolved_at",
            "resolved_by",
            "resolved_by_email",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "session_code",
            "session_starts_at",
            "room_code",
            "reporter_email",
            "reporter_name",
            "resolved_by_email",
            "reported_at",
        )
