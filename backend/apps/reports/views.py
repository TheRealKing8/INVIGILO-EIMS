"""Report viewsets.

Generation itself happens in ``apps.reports.tasks.generate_report`` (a
Celery task — in eager mode for tests). The HTTP surface is a thin
create-and-wait wrapper, plus a download endpoint that streams the
file.
"""
from __future__ import annotations

from django.http import FileResponse, Http404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.permissions import HasPermission

from .models import ReportExport
from .serializers import ReportExportSerializer


@extend_schema(tags=["reports"])
class ReportExportViewSet(viewsets.ReadOnlyModelViewSet):
    """List + retrieve report exports; create + download via actions."""

    queryset = ReportExport.objects.select_related("cycle", "generated_by")
    serializer_class = ReportExportSerializer
    permission_classes = [HasPermission.with_codes("report.view")]
    filterset_fields = ("format", "audience", "cycle")
    ordering = ("-generated_at",)
    search_fields = ("title",)

    @extend_schema(
        tags=["reports"],
        summary="Generate a new report export (async via Celery, eager in tests).",
        request={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "format": {"type": "string", "enum": ["pdf", "excel", "csv"]},
                "audience": {"type": "string"},
                "cycle_id": {"type": "string", "format": "uuid"},
                "model": {"type": "string"},
            },
            "required": ["title", "format"],
        },
        responses={201: ReportExportSerializer},
    )
    def create(self, request, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not request.user.has_permission("report.export"):
            from apps.core.exceptions import PermissionDeniedError
            raise PermissionDeniedError("You do not have permission to generate exports.")

        title = request.data.get("title")
        fmt = request.data.get("format")
        if not title or fmt not in {f for f, _ in ReportExport.FORMAT_CHOICES}:
            raise ValidationError({"detail": "title and a valid format are required."})

        cycle_id = request.data.get("cycle_id")
        export = ReportExport.objects.create(
            title=title,
            format=fmt,
            audience=request.data.get("audience", "internal"),
            cycle_id=cycle_id or None,
            generated_by=request.user,
            parameters=request.data.get("parameters", {}),
        )
        # Eager-mode in tests; production runs in worker.
        from .tasks import generate_report
        generate_report.apply(args=(str(export.id),))
        export.refresh_from_db()
        return Response(self.get_serializer(export).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["reports"],
        summary="Stream the export's file body.",
        responses={200: OpenApiResponse(description="The export file")},
    )
    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):  # type: ignore[no-untyped-def]
        export = self.get_object()
        if not export.file:
            raise Http404("No file attached to this export yet.")
        try:
            response = FileResponse(export.file.open("rb"), as_attachment=True)
            response["Content-Disposition"] = (
                f'attachment; filename="{export.title}.{export.format}"'
            )
            return response
        except FileNotFoundError:
            raise Http404("The export file is missing on disk.")
