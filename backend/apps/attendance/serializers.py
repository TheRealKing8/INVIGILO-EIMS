"""DRF serializers for the attendance app."""
from __future__ import annotations

from rest_framework import serializers

from .models import CheckIn


class CheckInSerializer(serializers.ModelSerializer):
    """A single check-in row.

    Read-only denormalised fields are exposed for the frontend so it
    can render "Alice — present at 09:02 (self)" without a second
    round-trip to /users/.
    """

    user_email = serializers.CharField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    recorded_by_email = serializers.CharField(source="recorded_by.email", read_only=True)
    session_code = serializers.CharField(source="session.course.code", read_only=True)
    session_starts_at = serializers.DateTimeField(source="session.starts_at", read_only=True)

    class Meta:
        model = CheckIn
        fields = (
            "id",
            "session",
            "session_code",
            "session_starts_at",
            "user",
            "user_email",
            "user_name",
            "kind",
            "method",
            "at",
            "late",
            "location",
            "recorded_by",
            "recorded_by_email",
            "signature_image",
            "created_at",
        )
        read_only_fields = (
            "id",
            "at",
            "late",
            "recorded_by",
            "recorded_by_email",
            "user_email",
            "user_name",
            "session_code",
            "session_starts_at",
            "created_at",
        )


class SelfCheckInSerializer(serializers.Serializer):
    """Body for ``POST /attendance/checkin/``.

    Validates that the user is allowed to self check-in to this
    session: they must be a confirmed allocation on the session (for
    invigilator) or the session must be open (for student; we don't
    track student registrations at the row level, so any
    authenticated student with the right perm may check in to any
    scheduled session — the exam office trusts the student not to
    spoof this).
    """

    session_id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=CheckIn.Kind.choices)
    location = serializers.CharField(
        max_length=120, required=False, allow_blank=True, default=""
    )


class BulkCheckInEntrySerializer(serializers.Serializer):
    """One entry inside a bulk check-in body."""

    user_id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=CheckIn.Kind.choices)
    late = serializers.BooleanField(required=False, default=False)
    location = serializers.CharField(
        max_length=120, required=False, allow_blank=True, default=""
    )
    # Base64 PNG (with or without the data-URL prefix). The
    # ``normalise_signature`` helper in services.py strips the prefix
    # and validates the payload. Optional — bulk entries that don't
    # need a signature just omit the field.
    signature_png = serializers.CharField(
        required=False, allow_blank=True, default=""
    )


class BulkCheckInSerializer(serializers.Serializer):
    """Body for ``POST /attendance/sessions/{id}/bulk-checkin/``."""

    entries = BulkCheckInEntrySerializer(many=True, allow_empty=False)


class ScanSerializer(serializers.Serializer):
    """Body for ``POST /attendance/scan/`` — security officer scans a
    student's QR (or types their student code) to check them in.

    The ``session_id`` + ``registration_id`` pair is looked up in
    :class:`StudentRegistration`; the resolved user is the one
    checked in. The signature is optional.
    """

    session_id = serializers.UUIDField()
    registration_id = serializers.UUIDField()
    location = serializers.CharField(
        max_length=120, required=False, allow_blank=True, default=""
    )
    signature_png = serializers.CharField(
        required=False, allow_blank=True, default=""
    )


__all__ = [
    "BulkCheckInEntrySerializer",
    "BulkCheckInSerializer",
    "CheckInSerializer",
    "ScanSerializer",
    "SelfCheckInSerializer",
]
