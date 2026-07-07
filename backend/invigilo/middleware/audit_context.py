"""Bind the authenticated user to a thread-local so audit calls can find them.

The audit layer (added in a later phase) reads ``audit_context.get_actor()``
to attribute writes. Centralising the binding in a middleware keeps the
audit helper ignorant of the request lifecycle.
"""
from __future__ import annotations

import contextvars
from typing import Any, Callable

from django.http import HttpRequest, HttpResponse

_actor_var: contextvars.ContextVar[Any] = contextvars.ContextVar("invigilo_actor", default=None)


def get_actor() -> Any:
    """Return the current request's user, or ``None``."""
    return _actor_var.get()


def set_actor(actor: Any) -> contextvars.Token:
    """Bind an actor for the current task/request."""
    return _actor_var.set(actor)


def reset_actor(token: contextvars.Token) -> None:
    _actor_var.reset(token)


class AuditContextMiddleware:
    """Bind ``request.user`` to the audit context for the duration of the request."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        token = set_actor(user if user and user.is_authenticated else None)
        try:
            return self.get_response(request)
        finally:
            reset_actor(token)
