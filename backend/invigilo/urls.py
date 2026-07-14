"""Project URL configuration.

The actual API routes are mounted by each app's ``urls.py``; this file is
responsible for top-level wiring and OpenAPI documentation.
"""
from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


def root(_request):  # type: ignore[no-untyped-def]
    """Landing endpoint for the API root."""
    return JsonResponse(
        {
            "name": "INVIGILO API",
            "version": "0.1.0",
            "docs": "/api/docs/",
            "schema": "/api/schema/",
            "health": "/api/health/",
            "ready": "/api/ready/",
        }
    )


api_v1_patterns = [
    path("auth/", include(("apps.accounts.urls", "accounts"), namespace="auth")),
    path("users/", include(("apps.accounts.urls_users", "accounts_users"), namespace="users")),
    path("academic/", include(("apps.academic.urls", "academic"), namespace="academic")),
    path("rooms/", include(("apps.rooms.urls", "rooms"), namespace="rooms")),
    path("exams/", include(("apps.exams.urls", "exams"), namespace="exams")),
    path(
        "invigilators/",
        include(("apps.invigilators.urls", "invigilators"), namespace="invigilators"),
    ),
    path(
        "allocations/",
        include(("apps.allocations.urls", "allocations"), namespace="allocations"),
    ),
    path("incidents/", include(("apps.incidents.urls", "incidents"), namespace="incidents")),
    path(
        "attendance/",
        include(("apps.attendance.urls", "attendance"), namespace="attendance"),
    ),
    path("reports/", include(("apps.reports.urls", "reports"), namespace="reports")),
    path("audit/", include(("apps.audit.urls", "audit"), namespace="audit")),
    path("ai/", include(("apps.ai.urls", "ai"), namespace="ai")),
]

urlpatterns = [
    path("", root),
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1_patterns)),
    # OpenAPI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

# Health checks are mounted at the top level (not /api/v1/) so probes can
# hit them without going through API versioning.
urlpatterns += [
    path("api/health/", include(("apps.core.urls_health", "core_health"), namespace="health")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
