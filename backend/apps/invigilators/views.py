from drf_spectacular.utils import extend_schema
from rest_framework import viewsets

from apps.core.permissions import HasPermission

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


@extend_schema(tags=["invigilators"])
class AvailabilityViewSet(viewsets.ModelViewSet):
    queryset = Availability.objects.select_related("invigilator__user")
    serializer_class = AvailabilitySerializer
    permission_classes = [HasPermission.with_codes("people.invigilator.crud")]
    filterset_fields = ("status", "date", "invigilator")
    ordering = ("date",)
