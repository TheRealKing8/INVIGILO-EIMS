from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import PermissionDeniedError
from apps.core.permissions import HasPermission

from .models import Incident
from .serializers import IncidentSerializer


@extend_schema(tags=["incidents"])
class IncidentViewSet(viewsets.ModelViewSet):
    queryset = Incident.objects.select_related("session__course", "reporter", "resolved_by")
    serializer_class = IncidentSerializer
    permission_classes = [HasPermission.with_codes("incident.view")]
    filterset_fields = ("status", "severity", "session", "reporter")
    ordering = ("-reported_at",)
    search_fields = ("title", "body", "session__course__code")

    def get_queryset(self):  # type: ignore[no-untyped-def]
        qs = super().get_queryset()
        # INVIGILATOR role can only see incidents they reported.
        user = self.request.user
        if not user or not user.is_authenticated:
            return qs.none()
        if user.is_superuser or user.is_staff:
            return qs
        if user.has_role("INVIGILATOR") and not user.has_role("EXAMINATION_OFFICER"):
            return qs.filter(reporter=user)
        return qs

    def perform_create(self, serializer):  # type: ignore[no-untyped-def]
        # Invigilators are allowed to create; permission is enforced by the
        # global IncidentViewSet permission class plus the row-scoping above.
        serializer.save(reporter=self.request.user)

    @extend_schema(
        tags=["incidents"],
        summary="Move an incident to a new status (chief/officer only).",
        request={"type": "object", "properties": {"status": {"type": "string"}}},
        responses={200: IncidentSerializer},
    )
    @action(detail=True, methods=["patch"], url_path="status")
    def set_status(self, request, pk=None):  # type: ignore[no-untyped-def]
        incident = self.get_object()
        if not request.user.has_permission("incident.update_status"):
            raise PermissionDeniedError("You do not have permission to update incident status.")
        new_status = request.data.get("status")
        if new_status not in {s for s, _ in Incident.STATUS_CHOICES}:
            return Response(
                {"detail": f"Invalid status: {new_status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        incident.status = new_status
        if new_status == "resolved" and not incident.resolved_at:
            from django.utils import timezone

            incident.resolved_at = timezone.now()
            incident.resolved_by = request.user
        incident.save(update_fields=("status", "resolved_at", "resolved_by", "updated_at"))

        # Fire in-app notifications on escalations and resolutions. We
        # do the lookup inside the view (not a signal) because the
        # target user is "the chief for this incident" — derived from
        # roles, not a FK on the row.
        if new_status in {"escalated", "resolved"}:
            from apps.accounts.models import Role
            from apps.notifications.services import notify

            targets: list = []
            if new_status == "escalated":
                # Notify every active EXAMINATION_OFFICER — they're
                # the ones who'll pick it up.
                eo_role = Role.objects.filter(code="EXAMINATION_OFFICER", is_active=True).first()
                if eo_role is not None:
                    targets = list(
                        eo_role.role_users.select_related("user").all()
                    )
                    targets = [ru.user for ru in targets]
            elif new_status == "resolved":
                # Notify the reporter (so they know it's closed).
                if incident.reporter_id:
                    targets = [incident.reporter]

            for user in targets:
                notify(
                    recipient=user,
                    kind=f"incident.{new_status}",
                    title=f"Incident {new_status}: {incident.title}",
                    body=(
                        f"Incident {incident.id} on {incident.session.course.code if incident.session else 'no session'} "
                        f"moved to {new_status}."
                    ),
                    target_type="Incident",
                    target_id=str(incident.id),
                )

        return Response(self.get_serializer(incident).data)
