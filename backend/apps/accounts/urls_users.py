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
    # Elevated actions — the method-level permission split in
    # ``UserViewSet.get_permissions`` tightens these to their own
    # narrower codename. Listed here last so the routes above remain
    # the primary list/create/retrieve/update/destroy surface.
    path(
        "<uuid:pk>/reset-password/",
        _bind("post", "reset_password"),
        name="users-reset-password",
    ),
    path(
        "<uuid:pk>/set-roles/",
        _bind("post", "set_roles"),
        name="users-set-roles",
    ),
]
