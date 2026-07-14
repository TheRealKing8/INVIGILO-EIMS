"""Serializers for the notification feed."""
from __future__ import annotations

from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """One row of the user's feed. ``recipient_email`` is denormalised
    so the frontend doesn't have to follow an FK just to label the
    row (it does the same for the audit log)."""

    recipient_email = serializers.EmailField(source="recipient.email", read_only=True)
    target_url = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            "id",
            "kind",
            "title",
            "body",
            "target_type",
            "target_id",
            "target_url",
            "is_read",
            "read_at",
            "email_sent_at",
            "email_failed",
            "recipient_email",
            "created_at",
        )
        read_only_fields = fields

    def get_target_url(self, obj: Notification) -> str:
        """Map a (target_type, target_id) pair to a frontend URL.

        The frontend renders these as link buttons on the feed page.
        Unknown target types return ``""`` so the link is just hidden
        rather than a 404.
        """
        if not obj.target_id:
            return ""
        mapping = {
            "Allocation": f"/dashboard/allocations/{obj.target_id}",
            "ExamSession": f"/dashboard/exams/{obj.target_id}",
            "Incident": f"/dashboard/incident/{obj.target_id}",
        }
        return mapping.get(obj.target_type, "")


__all__ = ["NotificationSerializer"]
