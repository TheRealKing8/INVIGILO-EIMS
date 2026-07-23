"""URL configuration for ``/api/v1/users/``."""
from __future__ import annotations

from django.urls import path

from .views import UserViewSet


def _bind(methods: dict[str, str]):  # type: ignore[no-untyped-def]
    """Bind one or more HTTP methods on a ViewSet to a single URL pattern.

    Each ``UserViewSet`` action needs its own URL pattern so the method
    dispatch table can hand ``GET`` to ``list``/``retrieve`` and
    ``POST``/``PATCH``/``DELETE`` to ``create``/``partial_update``/
    ``destroy``. When two ``path("")`` or two ``path("<uuid:pk>/")``
    entries exist, Django's URL resolver returns the *first* match for
    every request — so a ``POST /api/v1/users/`` would always hit the
    GET-only ``list`` view and return 405. Binding all methods of an
    action set to one path fixes the dispatch.
    """
    return UserViewSet.as_view(methods)


urlpatterns = [
    # /api/v1/users/ — list (GET) and create (POST) on the same path.
    # Combining them on one route is the only way to make POST dispatch
    # work; the older two-entry pattern always 405'd on POST.
    path(
        "",
        _bind({"get": "list", "post": "create"}),
        name="users-list",
    ),
    # /api/v1/users/{id}/ — retrieve (GET), partial_update (PATCH),
    # and destroy (DELETE). Same reason as above; DELETE was the
    # silent-405 victim of the old split.
    path(
        "<uuid:pk>/",
        _bind({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="users-retrieve",
    ),
    # Action endpoints (single HTTP verb, single ViewSet method).
    path(
        "<uuid:pk>/unlock/",
        _bind({"post": "unlock"}),
        name="users-unlock",
    ),
    # Elevated actions — the method-level permission split in
    # ``UserViewSet.get_permissions`` tightens these to their own
    # narrower codename. Listed here last so the routes above remain
    # the primary list/create/retrieve/update/destroy surface.
    path(
        "<uuid:pk>/reset-password/",
        _bind({"post": "reset_password"}),
        name="users-reset-password",
    ),
    path(
        "<uuid:pk>/set-roles/",
        _bind({"post": "set_roles"}),
        name="users-set-roles",
    ),
]
