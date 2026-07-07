"""URL configuration for ``/api/v1/users/``."""
from __future__ import annotations

from django.urls import path

from .views import UserViewSet


def _bind(method: str, name: str):  # type: ignore[no-untyped-def]
    view = UserViewSet.as_view({method: name})
    return view


urlpatterns = [
    path("", _bind("get", "list"), name="users-list"),
    path("", _bind("post", "create"), name="users-create"),
    path("<uuid:pk>/", _bind("get", "retrieve"), name="users-retrieve"),
    path("<uuid:pk>/", _bind("patch", "partial_update"), name="users-update"),
    path("<uuid:pk>/", _bind("delete", "destroy"), name="users-destroy"),
    path("<uuid:pk>/unlock/", _bind("post", "unlock"), name="users-unlock"),
]
