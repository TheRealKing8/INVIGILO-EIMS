"""Attendance / check-in API.

The endpoint surface is small and intentionally write-light:

  * ``POST /attendance/checkin/``  — invigilator or student says "I'm here".
  * ``POST /attendance/sessions/{id}/bulk-checkin/`` — security officer
    runs the door roster and marks multiple people in one call.
  * ``GET  /attendance/sessions/{id}/roster/`` — JSON roster.
  * ``GET  /attendance/sessions/{id}/export.csv`` — CSV export for the
    record (function-based view, see ``apps.attendance.exports``).

There is no DELETE / PATCH — check-ins are append-only. A second
self check-in for the same person + session + kind is a no-op that
returns the existing row.
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.allocations.models import Allocation
from apps.core.permissions import HasPermission
from apps.exams.models import ExamSession

from .models import CheckIn
from .serializers import (
    BulkCheckInSerializer,
    CheckInSerializer,
    SelfCheckInSerializer,
)
from .services import build_roster, compute_late


@extend_schema(tags=["attendance"])
class CheckInViewSet(viewsets.GenericViewSet):
    """Append-only check-in API.

    The base permission is :class:`IsAuthenticated` — every action
    needs a logged-in user, but the specific codename check happens
    inside the action (self check-in needs ``checkin_own``;
    bulk check-in needs ``checkin_any``; the roster needs
    ``view``). The viewset doesn't enforce ``attendance.view`` at
    the class level because STUDENT doesn't hold that codename —
    a student checking in to a session is a legitimate action even
    though they can't see the full roster.
    """

    queryset = CheckIn.objects.select_related("user", "session__course", "recorded_by")
    serializer_class = CheckInSerializer
    permission_classes = [IsAuthenticated]
    # The router is mounted at the empty prefix, so we deliberately
    # disable the default ``/{id}/`` detail route by overriding
    # ``lookup_value_regex`` to a never-matching sentinel. The only
    # way to reach a specific session is via the explicit
    # ``sessions/{id}/...`` action URLs.
    lookup_value_regex = r"__never_match__"

    # ------------------------------------------------------------------
    # Self check-in
    # ------------------------------------------------------------------
    @extend_schema(
        tags=["attendance"],
        summary="Invigilator or student self check-in for a session.",
        request=SelfCheckInSerializer,
        responses={
            201: CheckInSerializer,
            200: OpenApiResponse(
                response=CheckInSerializer,
                description="Already checked in — the existing row is returned.",
            ),
            403: OpenApiResponse(description="Not an accepted allocation on the session."),
        },
    )
    def create(self, request):  # type: ignore[no-untyped-def]
        # POST /attendance/ — self check-in. Validated as
        # SelfCheckInSerializer (not the ModelSerializer) so the
        # session_id comes through as a top-level field.
        return self._self_checkin(request)

    # ------------------------------------------------------------------
    # Bulk check-in (security officer)
    # ------------------------------------------------------------------
    @extend_schema(
        tags=["attendance"],
        summary="Security officer: mark several people in at the door.",
        request=BulkCheckInSerializer,
        responses={200: OpenApiResponse(description="`{created, already}` counts.")},
    )
    @action(
        detail=False,
        methods=["post"],
        url_path=r"sessions/(?P<session_id>[^/.]+)/bulk-checkin",
        permission_classes=[HasPermission.with_codes("attendance.checkin_any")],
    )
    def bulk_checkin(self, request, session_id=None):  # type: ignore[no-untyped-def]
        session = get_object_or_404(ExamSession, id=session_id)
        body = BulkCheckInSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        created = 0
        already = 0
        now = timezone.now()
        from django.contrib.auth import get_user_model

        User = get_user_model()
        for entry in body.validated_data["entries"]:
            try:
                user = User.objects.get(id=entry["user_id"])
            except User.DoesNotExist:
                raise ValidationError(
                    {"entries": f"Unknown user_id: {entry['user_id']}"}
                )
            row, was_created = CheckIn.objects.get_or_create(
                session=session,
                user=user,
                kind=entry["kind"],
                defaults={
                    "method": CheckIn.Method.BULK,
                    "late": entry.get("late", compute_late(session, now)),
                    "location": entry.get("location", ""),
                    "recorded_by": request.user,
                },
            )
            if was_created:
                created += 1
            else:
                already += 1
        return Response({"created": created, "already": already})

    # ------------------------------------------------------------------
    # Roster view (JSON)
    # ------------------------------------------------------------------
    @extend_schema(
        tags=["attendance"],
        summary="Roster for one exam session (invigilators and students).",
        responses={200: OpenApiResponse(description="Roster payload.")},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path=r"sessions/(?P<session_id>[^/.]+)/roster",
        permission_classes=[HasPermission.with_codes("attendance.view")],
    )
    def session_roster(self, request, session_id=None):  # type: ignore[no-untyped-def]
        session = get_object_or_404(ExamSession, id=session_id)
        return Response(build_roster(session))

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _self_checkin(self, request):  # type: ignore[no-untyped-def]
        if not request.user.has_permission("attendance.checkin_own"):
            raise PermissionDenied("You do not have permission to check in.")
        body = SelfCheckInSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        session = get_object_or_404(ExamSession, id=body.validated_data["session_id"])
        kind = body.validated_data["kind"]

        if kind == CheckIn.Kind.INVIGILATOR:
            is_allocated = Allocation.objects.filter(
                session=session,
                invigilator__user=request.user,
                status="confirmed",
            ).exists()
            if not is_allocated:
                raise PermissionDenied(
                    "You are not an allocated invigilator on this session."
                )

        now = timezone.now()
        return self._upsert(
            session=session,
            user=request.user,
            kind=kind,
            method=CheckIn.Method.SELF,
            late=compute_late(session, now),
            location=body.validated_data.get("location", ""),
            recorded_by=request.user,
            now=now,
        )

    def _upsert(self, *, session, user, kind, method, late, location, recorded_by, now):  # type: ignore[no-untyped-def]
        """get_or_create the row, returning the JSON response.

        We never overwrite an existing row — the first check-in wins.
        A second self check-in is a no-op (200 with the existing row)
        rather than a 409, so the frontend can be idempotent.
        """
        row, created = CheckIn.objects.get_or_create(
            session=session,
            user=user,
            kind=kind,
            defaults={
                "method": method,
                "late": late,
                "location": location,
                "recorded_by": recorded_by,
            },
        )
        body = CheckInSerializer(row).data
        return Response(
            body,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


__all__ = ["CheckInViewSet"]
