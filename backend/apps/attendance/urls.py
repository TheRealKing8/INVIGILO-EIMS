"""URL configuration for the attendance app.

The viewset's actions give us::

  * POST /api/v1/attendance/                              → self check-in
  * POST /api/v1/attendance/sessions/{id}/bulk-checkin/   → security bulk
  * GET  /api/v1/attendance/sessions/{id}/roster/         → JSON roster

The CSV export is mounted as a function-based view so the URL can
carry a literal ``.csv`` suffix without fighting DRF's
format-suffix router (which would otherwise make ``export.csv``
look like a format-suffix variant of the previous path segment).
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from .exports import export_session_csv
from .views import CheckInViewSet

router = DefaultRouter()
router.register(r"", CheckInViewSet, basename="checkin")

urlpatterns = router.urls + [
    path(
        "sessions/<uuid:session_id>/export.csv",
        export_session_csv,
        name="attendance-export-csv",
    ),
]
