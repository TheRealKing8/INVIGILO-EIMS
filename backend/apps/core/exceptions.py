"""Domain exception hierarchy.

The DRF exception handler in ``exceptions_handler.py`` turns every
``DomainError`` into a structured JSON response with ``error``,
``detail`` and (optionally) ``code`` fields. Code in the service layer
raises these exceptions — it never returns a tuple of ``(ok, value)``.
"""
from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base class for every error raised by an INVIGILO service.

    Subclasses set ``status_code`` (default 400) and ``code`` (default
    a lower-snake-case version of the class name). The DRF exception
    handler uses these to produce the response.
    """

    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, detail: str | None = None, *, extra: dict[str, Any] | None = None) -> None:
        self.detail = detail or self.__class__.__doc__ or self.code
        self.extra = extra or {}
        super().__init__(self.detail)

    def to_payload(self) -> dict[str, Any]:
        return {"error": self.code, "detail": self.detail, **self.extra}


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class PermissionDeniedError(DomainError):
    status_code = 403
    code = "permission_denied"


class ValidationFailedError(DomainError):
    status_code = 422
    code = "validation_failed"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class AuthenticationError(DomainError):
    status_code = 401
    code = "authentication_failed"


class RateLimitedError(DomainError):
    status_code = 429
    code = "rate_limited"


__all__ = [
    "DomainError",
    "NotFoundError",
    "PermissionDeniedError",
    "ValidationFailedError",
    "ConflictError",
    "AuthenticationError",
    "RateLimitedError",
]
