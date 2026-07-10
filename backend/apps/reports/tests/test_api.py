"""Tests for the report-export endpoints."""
from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.reports.models import ReportExport


pytestmark = pytest.mark.django_db


def test_list_requires_auth(client: APIClient) -> None:
    assert client.get(reverse("reports:report-export-list")).status_code == 401


def test_unauthorized_cannot_create(
    client: APIClient, verified_user, grant_permission
) -> None:
    grant_permission(verified_user, "report.view")
    client.force_authenticate(verified_user)
    response = client.post(
        reverse("reports:report-export-list"),
        {"title": "My report", "format": "pdf"},
        format="json",
    )
    assert response.status_code == 403


def test_authorized_create_attaches_file(
    client: APIClient, verified_user, grant_permission
) -> None:
    grant_permission(verified_user, "report.view", "report.export")
    client.force_authenticate(verified_user)
    response = client.post(
        reverse("reports:report-export-list"),
        {"title": "Attendance summary", "format": "pdf"},
        format="json",
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["format"] == "pdf"
    # Eager mode: the Celery task ran inline and the file is attached.
    assert body["download_url"] is not None
    assert body["size_bytes"] > 0


def test_download_streams_file(
    client: APIClient, verified_user, grant_permission
) -> None:
    grant_permission(verified_user, "report.view", "report.export")
    client.force_authenticate(verified_user)
    create = client.post(
        reverse("reports:report-export-list"),
        {
            "title": "Workload",
            "format": "csv",
            "parameters": {"model": "incidents"},
        },
        format="json",
    ).json()
    response = client.get(reverse("reports:report-export-download", args=[create["id"]]))
    assert response.status_code == 200
    body = b"".join(response.streaming_content)
    # CSV renderer writes a header row.
    assert b"id,title,severity,status" in body


def test_download_unattached_returns_404(
    client: APIClient, verified_user, grant_permission
) -> None:
    grant_permission(verified_user, "report.view", "report.export")
    client.force_authenticate(verified_user)
    export = ReportExport.objects.create(
        title="Empty", format="pdf", generated_by=verified_user
    )
    response = client.get(reverse("reports:report-export-download", args=[export.id]))
    assert response.status_code == 404
