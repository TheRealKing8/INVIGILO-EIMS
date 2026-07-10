from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source="actor.email", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "actor",
            "actor_email",
            "action",
            "target_type",
            "target_id",
            "before",
            "after",
            "path",
            "method",
            "request_id",
            "created_at",
        )
        read_only_fields = fields
