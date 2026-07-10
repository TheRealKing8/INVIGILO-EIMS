"""Tests for the audit log read-only endpoint."""
from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog


pytestmark = pytest.mark.django_db


def test_unauthenticated_returns_401(client: APIClient) -> None:
    assert client.get(reverse("audit:audit-log-list")).status_code == 401


def test_officer_can_list(
    client: APIClient, verified_user, grant_permission, django_user_model
) -> None:
    grant_permission(verified_user, "audit.view")
    client.force_authenticate(verified_user)
    actor = django_user_model.objects.create_user(email="a@x.com", full_name="A")
    AuditLog.objects.create(actor=actor, action="create", target_type="ExamSession", target_id="x")
    response = client.get(reverse("audit:audit-log-list"))
    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_filter_by_target_type(
    client: APIClient, verified_user, grant_permission, django_user_model
) -> None:
    grant_permission(verified_user, "audit.view")
    client.force_authenticate(verified_user)
    actor = django_user_model.objects.create_user(email="a@x.com", full_name="A")
    AuditLog.objects.create(actor=actor, action="create", target_type="ExamSession", target_id="1")
    AuditLog.objects.create(actor=actor, action="create", target_type="Incident", target_id="2")
    response = client.get(reverse("audit:audit-log-list"), {"target_type": "Incident"})
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["target_type"] == "Incident"
