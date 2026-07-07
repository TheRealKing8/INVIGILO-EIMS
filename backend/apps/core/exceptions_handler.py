"""DRF exception handler for INVIGILO.

Renders :class:`apps.core.exceptions.DomainError` subclasses as a uniform
``{"error": "<code>", "detail": "<message>"}`` JSON response. Falls back
to DRF's default handler for everything else (validation errors,
throttled responses, etc.) so we don't lose their structure.
"""
from __future__ import annotations

import logging
from typing import Any

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.core.exceptions import DomainError

logger = logging.getLogger("invigilo.api")


def invigilo_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Render domain exceptions; delegate to DRF for everything else."""
    if isinstance(exc, DomainError):
        logger.warning(
            "Domain exception: %s — %s",
            exc.code,
            exc.detail,
            extra={"path": context.get("request").path if context.get("request") else None},
        )
        return Response(exc.to_payload(), status=exc.status_code)
    return drf_exception_handler(exc, context)
