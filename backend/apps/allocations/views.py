"""Allocation viewsets and the engine endpoints.

The actual greedy engine lives in ``services.engine``. This module
exposes the HTTP surface and delegates to it.
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.permissions import HasPermission

from .models import Allocation, AllocationRun, Conflict
from .serializers import (
    AllocationRunSerializer,
    AllocationSerializer,
    ConflictSerializer,
)
from .services import run_engine


@extend_schema(tags=["allocations"])
class AllocationViewSet(viewsets.ModelViewSet):
    queryset = Allocation.objects.select_related(
        "session__course",
        "invigilator__user",
        "invigilator__primary_department",
        "room__building",
        "run",
    )
    serializer_class = AllocationSerializer
    permission_classes = [HasPermission.with_codes("allocator.run")]
    filterset_fields = ("status", "session", "invigilator", "run", "role")
    ordering = ("session__starts_at",)
    search_fields = (
        "invigilator__user__email",
        "invigilator__user__full_name",
        "session__course__code",
    )

    @extend_schema(
        tags=["allocations"],
        summary="Swap an invigilator on an existing allocation.",
        request={
            "type": "object",
            "properties": {"invigilator_id": {"type": "string", "format": "uuid"}},
            "required": ["invigilator_id"],
        },
        responses={200: AllocationSerializer},
    )
    @action(detail=True, methods=["post"], url_path="reassign")
    def reassign(self, request, pk=None):  # type: ignore[no-untyped-def]
        if not request.user.has_permission("allocator.reassign"):
            from apps.core.exceptions import PermissionDeniedError

            raise PermissionDeniedError("You do not have permission to reassign.")
        allocation = self.get_object()
        new_inv_id = request.data.get("invigilator_id")
        if not new_inv_id:
            raise ValidationError({"invigilator_id": "Required."})
        from apps.invigilators.models import InvigilatorProfile

        try:
            new_profile = InvigilatorProfile.objects.get(pk=new_inv_id)
        except InvigilatorProfile.DoesNotExist as exc:
            raise ValidationError({"invigilator_id": "Unknown invigilator."}) from exc

        # Capture the previous invigilator so we can notify them
        # they're being moved off. The post_save signal handles the
        # *new* invigilator (allocation_created_or_changed in
        # ``apps.notifications.signals``); we handle the old one here
        # because post_save doesn't expose the pre-image FK.
        old_invigilator = allocation.invigilator
        allocation.invigilator = new_profile
        allocation.save(update_fields=("invigilator", "updated_at"))

        if old_invigilator.pk != new_profile.pk:
            from apps.notifications.services import notify

            notify(
                recipient=old_invigilator.user,
                kind="allocation.reassigned",
                title=f"Reassigned from {allocation.session.course.code}",
                body=(
                    f"You've been moved off {allocation.session.course.code} on "
                    f"{allocation.session.starts_at:%Y-%m-%d %H:%M}."
                ),
                target_type="Allocation",
                target_id=str(allocation.id),
            )

        return Response(self.get_serializer(allocation).data)


@extend_schema(tags=["allocations"])
class AllocationRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AllocationRun.objects.select_related("period", "triggered_by")
    serializer_class = AllocationRunSerializer
    permission_classes = [HasPermission.with_codes("allocator.run")]
    filterset_fields = ("period",)
    ordering = ("-created_at",)

    @extend_schema(
        tags=["allocations"],
        summary="Run the allocation engine against a period.",
        request={
            "type": "object",
            "properties": {"period_id": {"type": "string", "format": "uuid"}},
            "required": ["period_id"],
        },
        responses={201: AllocationRunSerializer},
    )
    def create(self, request, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not request.user.has_permission("allocator.run"):
            from apps.core.exceptions import PermissionDeniedError

            raise PermissionDeniedError("You do not have permission to run the engine.")
        period_id = request.data.get("period_id")
        if not period_id:
            raise ValidationError({"period_id": "Required."})
        from apps.exams.models import ExamPeriod

        try:
            period = ExamPeriod.objects.get(pk=period_id)
        except ExamPeriod.DoesNotExist as exc:
            raise ValidationError({"period_id": "Unknown period."}) from exc
        run = run_engine(period, triggered_by=request.user)
        return Response(self.get_serializer(run).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["allocations"])
class ConflictViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Conflict.objects.select_related("run", "session__course", "invigilator__user")
    serializer_class = ConflictSerializer
    permission_classes = [HasPermission.with_codes("allocator.run")]
    filterset_fields = ("run", "type", "severity")
    ordering = ("-created_at",)
