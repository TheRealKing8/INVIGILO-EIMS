"""URL config for the analytics app.

Mounted at ``/api/v1/analytics/`` from :mod:`invigilo.urls`. The
single endpoint lives at ``/api/v1/analytics/summary/``.
"""
from django.urls import path

from .views import AnalyticsSummaryView


urlpatterns = [
    path("summary/", AnalyticsSummaryView.as_view(), name="analytics-summary"),
]


__all__ = ["urlpatterns"]
