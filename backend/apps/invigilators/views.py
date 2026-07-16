from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import HasPermission
from apps.exams.qr import qr_png_response
from apps.exams.qr_tokens import issue_staff_qr_token

from .models import Availability, InvigilatorProfile
from .serializers import (
    AvailabilitySerializer,
    InvigilatorProfileSerializer,
)


@extend_schema(tags=["invigilators"])
class InvigilatorProfileViewSet(viewsets.ModelViewSet):
    queryset = InvigilatorProfile.objects.select_related("user", "primary_department", "primary_department__faculty")
    serializer_class = InvigilatorProfileSerializer
    permission_classes = [HasPermission.with_codes("people.invigilator.crud")]
    filterset_fields = ("is_active", "primary_department", "rating")
    search_fields = ("user__email", "user__full_name")
    ordering_fields = ("user__full_name", "rating", "max_sessions_per_cycle")

    @extend_schema(
        tags=["invigilators"],
        summary="Printable staff QR code (PNG) for the current user.",
        description=(
            "Returns a PNG QR encoding a *signed* token bound to the "
            "caller. Used by invigilators / EOs / admins to check "
            "themselves in to rooms they are staffing. The token is "
            "rotated on a 5-minute TTL; clients should re-fetch the PNG "
            "on every page load."
        ),
        responses={200: OpenApiResponse(description="PNG image.")},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="me/qr.png",
        permission_classes=[IsAuthenticated],
    )
    def my_qr(self, request):  # type: ignore[no-untyped-def]
        # Any authenticated user can fetch their own staff QR — a
        # security officer on the day isn't necessarily an
        # invigilator in the database, but they're still staff who
        # need to scan in.
        raw, _ = issue_staff_qr_token(request.user)
        return qr_png_response(raw)

    @extend_schema(
        tags=["invigilators"],
        summary="Printable staff QR code (PNG) for an invigilator profile.",
        description=(
            "Returns a PNG QR encoding a *signed* token bound to the "
            "named invigilator profile. Use this to fetch *another* "
            "invigilator's QR (admin/EO verification flow) — the token "
            "is still minted for the named user, so a screenshot of the "
            "PNG scans in as *them*, not the viewer. Restricted to "
            "users with ``people.invigilator.crud``."
        ),
        responses={200: OpenApiResponse(description="PNG image.")},
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="qr.png",
    )
    def staff_qr(self, request, pk=None):  # type: ignore[no-untyped-def]
        # ``get_object()`` is the standard DRF hook that also runs
        # the queryset filter and the lookup. We rely on the class
        # permission (``people.invigilator.crud``) for the gate;
        # the token is minted for the *target* user, not the caller.
        profile = self.get_object()
        if profile.user_id is None:
            return Response(
                {"detail": "Invigilator profile is not linked to a user."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        raw, _ = issue_staff_qr_token(profile.user)
        return qr_png_response(raw)


@extend_schema(tags=["invigilators"])
class AvailabilityViewSet(viewsets.ModelViewSet):
    queryset = Availability.objects.select_related("invigilator__user")
    serializer_class = AvailabilitySerializer
    permission_classes = [HasPermission.with_codes("people.invigilator.crud")]
    filterset_fields = ("status", "date", "invigilator")
    ordering = ("date",)
