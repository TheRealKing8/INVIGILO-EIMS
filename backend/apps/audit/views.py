from drf_spectacular.utils import extend_schema
from rest_framework import viewsets

from apps.core.permissions import HasPermission

from .models import AuditLog
from .serializers import AuditLogSerializer


@extend_schema(tags=["audit"])
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("actor")
    serializer_class = AuditLogSerializer
    permission_classes = [HasPermission.with_codes("audit.view")]
    filterset_fields = ("action", "target_type", "actor")
    ordering = ("-created_at",)
    search_fields = ("target_id", "action")
