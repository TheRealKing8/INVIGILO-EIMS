"""Assign a request id and propagate it through the response and logs."""
from __future__ import annotations

import logging
import uuid
from typing import Callable

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("invigilo.request")

REQUEST_ID_HEADER = "HTTP_X_REQUEST_ID"
RESPONSE_HEADER = "X-Request-ID"


class RequestIDMiddleware:
    """Read or generate a request id, attach it to the log context, echo it back."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = request.META.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.request_id = request_id  # type: ignore[attr-defined]
        # Bound to the log record by the filter below; here we just stash it.
        response = self.get_response(request)
        response[RESPONSE_HEADER] = request_id
        return response


class RequestIDLogFilter(logging.Filter):
    """Copy the request id from the local thread onto each log record."""

    def __init__(self) -> None:
        super().__init__()
        self._current: str | None = None

    def bind(self, request_id: str) -> None:
        self._current = request_id

    def clear(self) -> None:
        self._current = None

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        if self._current:
            record.request_id = self._current  # type: ignore[attr-defined]
        return True
