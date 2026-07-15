"""HTTP layer for the analytics dashboard.

A single GET endpoint — :class:`AnalyticsSummaryView` — returns the
flat dict the frontend renders. We use a plain :class:`APIView` (not
a ViewSet) because there's no resource to list / retrieve / mutate;
the data is computed on demand from the other apps' tables.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import HasPermission

from .serializers import AnalyticsSummarySerializer
from .services import build_summary


def _summary_to_dict(ctx) -> dict:
    """Translate the dataclass into the JSON shape the serializer
    validates. Kept out of ``services.py`` so that module doesn't
    have to know about the HTTP contract.
    """
    return {
        "period_code": ctx.period.code if ctx.period else None,
        "period_name": ctx.period.name if ctx.period else None,
        "coverage": ctx.coverage,
        "upcoming_sessions_count": ctx.upcoming_sessions_count,
        "checkins_today": ctx.checkins_today,
        "late_count_today": ctx.late_count_today,
        "open_incidents_count": ctx.open_incidents_count,
        "invigilator_workload": ctx.invigilator_workload,
        "attendance_trend": ctx.attendance_trend,
        "sessions_by_day": ctx.sessions_by_day,
        "incidents_by_severity": ctx.incidents_by_severity,
        "generated_at": ctx.generated_at,
    }


@extend_schema(
    tags=["analytics"],
    summary="Aggregated KPIs for the analytics dashboard.",
    description=(
        "Single read endpoint that returns coverage, today's check-in "
        "counts, open incidents, the top-5 invigilator workload, the "
        "12-week attendance trend, the next 7 days of sessions grouped "
        "by day, and the incident severity breakdown. INVIGILATOR role "
        "gets their own workload only; operations roles see the full "
        "org-wide view. Permission: ``analytics.view``."
    ),
    responses={200: AnalyticsSummarySerializer},
)
class AnalyticsSummaryView(APIView):
    permission_classes = [IsAuthenticated, HasPermission.with_codes("analytics.view")]

    def get(self, request):  # type: ignore[no-untyped-def]
        ctx = build_summary(request.user)
        # Run the response through the serializer so the OpenAPI
        # schema describes it accurately and any shape drift is
        # caught by the test suite.
        data = AnalyticsSummarySerializer(_summary_to_dict(ctx)).data
        return Response(data)


__all__ = ["AnalyticsSummaryView"]
