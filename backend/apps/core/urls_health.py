"""URL config for the health endpoints."""
from __future__ import annotations

from django.urls import path

from .views_health import liveness, readiness

urlpatterns = [
    path("", liveness, name="health"),
    path("ready/", readiness, name="ready"),
]
