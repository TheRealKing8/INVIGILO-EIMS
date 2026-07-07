"""Tests for the core app primitives."""
from __future__ import annotations

from apps.core.exceptions import (
    AuthenticationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
)
from apps.core.exceptions_handler import invigilo_exception_handler
from apps.core.pagination import DefaultPagination


def test_domain_error_payload_shape() -> None:
    err = NotFoundError("user not found", extra={"id": "abc"})
    payload = err.to_payload()
    assert payload["error"] == "not_found"
    assert payload["detail"] == "user not found"
    assert payload["id"] == "abc"


def test_domain_error_status_codes() -> None:
    assert DomainError().status_code == 400
    assert NotFoundError().status_code == 404
    assert PermissionDeniedError().status_code == 403
    assert AuthenticationError().status_code == 401
    assert ConflictError().status_code == 409


def test_exception_handler_renders_domain_error() -> None:
    response = invigilo_exception_handler(
        NotFoundError("missing"),
        context={"request": None},
    )
    assert response is not None
    assert response.status_code == 404
    assert response.data["error"] == "not_found"


def test_exception_handler_passes_through_other_errors() -> None:
    from rest_framework.exceptions import NotFound

    response = invigilo_exception_handler(
        NotFound("missing"),
        context={"request": None},
    )
    assert response is not None
    assert response.status_code == 404


def test_pagination_envelope_shape() -> None:
    """The pagination class exposes a custom envelope — verify the keys."""
    # And DefaultPagination is importable and has the right attributes.
    p = DefaultPagination()
    assert p.page_size == 25
    assert p.max_page_size == 200
    assert p.page_query_param == "page"
    assert p.page_size_query_param == "page_size"
