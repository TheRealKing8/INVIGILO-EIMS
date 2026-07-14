"""Notification viewset + custom actions.

End-points (all require ``notification.view_own``):

* ``GET    /api/v1/notifications/``              — paginated feed.
* ``GET    /api/v1/notifications/{id}/``         — single row.
* ``POST   /api/v1/notifications/{id}/read/``    — mark one as read.
* ``POST   /api/v1/notifications/mark-all-read/``— mark everything as read.
* ``GET    /api/v1/notifications/unread-count/`` — topbar bell count.

The viewset is read-only at the model layer (``ReadOnlyModelViewSet``)
— the only writes are the ``is_read`` / ``read_at`` flips, which go
through the custom actions (so we can return the new count atomically
and have a single audit trail).
"""
from __future__ import annotations

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import HasPermission

from .models import Notification
from .serializers import NotificationSerializer


@extend_schema(tags=["notifications"])
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):  # type: ignore[type-arg]
    serializer_class = NotificationSerializer
    permission_classes = [HasPermission.with_codes("notification.view_own")]
    filterset_fields = ("kind", "is_read")
    ordering = ("-created_at",)
    search_fields = ("title", "body")

    def get_queryset(self) -> QuerySet[Notification]:  # type: ignore[override]
        """Restrict to the requesting user's own rows."""
        return Notification.objects.filter(recipient=self.request.user).order_by("-created_at")

    @extend_schema(
        tags=["notifications"],
        summary="Mark one notification as read.",
        request=None,
        responses={200: NotificationSerializer},
    )
    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):  # type: ignore[no-untyped-def]
        notif = get_object_or_404(self.get_queryset(), pk=pk)
        if not notif.is_read:
            notif.is_read = True
            notif.read_at = timezone.now()
            notif.save(update_fields=("is_read", "read_at", "updated_at"))
        return Response(self.get_serializer(notif).data)

    @extend_schema(
        tags=["notifications"],
        summary="Mark all of the user's unread notifications as read.",
        request=None,
        responses={200: OpenApiResponse(description="Returns the number updated.")},
    )
    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):  # type: ignore[no-untyped-def]
        now = timezone.now()
        updated = self.get_queryset().filter(is_read=False).update(is_read=True, read_at=now)
        return Response({"updated": updated})

    @extend_schema(
        tags=["notifications"],
        summary="Unread count for the topbar bell.",
        request=None,
        responses={200: OpenApiResponse(description="Returns {count: int}.")},
    )
    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):  # type: ignore[no-untyped-def]
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"count": count})


__all__ = ["NotificationViewSet"]
