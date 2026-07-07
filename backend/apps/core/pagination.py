"""Default pagination class for INVIGILO APIs.

The shape is::

    {
        "count": 1234,
        "page": 1,
        "page_size": 25,
        "total_pages": 50,
        "next": "?page=2",
        "previous": null,
        "results": [...]
    }

The full URL for ``next`` / ``previous`` is computed so the client can
just follow the link. The page size is bounded by the
``PAGE_SIZE`` / ``MAX_PAGE_SIZE`` settings.
"""
from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class DefaultPagination(PageNumberPagination):
    """Standard page-number paginator with a 25-row default and 200-row cap."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200
    page_query_param = "page"

    def get_paginated_response(self, data: list[Any]) -> Response:
        request = self.request
        full_path = request.build_absolute_uri()
        next_url = self.get_next_link()
        previous_url = self.get_previous_link()
        return Response(
            {
                "count": self.page.paginator.count,
                "page": self.page.number,
                "page_size": self.get_page_size(request),
                "total_pages": self.page.paginator.num_pages,
                "next": next_url,
                "previous": previous_url,
                "results": data,
            },
            status=status.HTTP_200_OK,
        )


__all__ = ["DefaultPagination"]
