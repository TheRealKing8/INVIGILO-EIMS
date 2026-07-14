"""Tests for the notification feed endpoints."""
from __future__ import annotations

import pytest
from django.core import mail
from django.urls import reverse
from rest_framework.test import APIClient

from apps.notifications.models import Notification
from apps.notifications.services import notify

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Auth / scope
# ---------------------------------------------------------------------------
def test_unauthenticated_returns_401(client: APIClient) -> None:
    response = client.get(reverse("notifications:notification-list"))
    assert response.status_code == 401


def test_list_returns_only_recipient_notifications(
    client: APIClient, verified_user, grant_permission
) -> None:
    grant_permission(verified_user, "notification.view_own")
    other = verified_user.__class__.objects.create_user(
        email="other@x.com",
        full_name="Other",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    # Use distinct target_ids so the get_or_create idempotency doesn't
    # collapse the three rows into one.
    notify(recipient=verified_user, kind="allocation.new", title="A", body="A body", target_id="tA")
    notify(recipient=verified_user, kind="allocation.new", title="B", body="B body", target_id="tB")
    notify(recipient=verified_user, kind="allocation.new", title="C", body="C body", target_id="tC")
    notify(recipient=other, kind="allocation.new", title="X", body="X body", target_id="tX")

    client.force_authenticate(verified_user)
    response = client.get(reverse("notifications:notification-list"))
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    titles = {row["title"] for row in body["results"]}
    assert titles == {"A", "B", "C"}


# ---------------------------------------------------------------------------
# Mark read
# ---------------------------------------------------------------------------
def test_mark_read_marks_one(
    client: APIClient, verified_user, grant_permission
) -> None:
    grant_permission(verified_user, "notification.view_own")
    n1 = notify(recipient=verified_user, kind="allocation.new", title="A", body="a", target_id="n1")
    n2 = notify(recipient=verified_user, kind="allocation.new", title="B", body="b", target_id="n2")
    n3 = notify(recipient=verified_user, kind="allocation.new", title="C", body="c", target_id="n3")
    client.force_authenticate(verified_user)

    response = client.post(
        reverse("notifications:notification-mark-read", args=[n1.id])
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_read"] is True
    assert body["read_at"] is not None

    n1.refresh_from_db()
    n2.refresh_from_db()
    n3.refresh_from_db()
    assert n1.is_read is True
    assert n2.is_read is False
    assert n3.is_read is False


def test_mark_all_read_returns_count(
    client: APIClient, verified_user, grant_permission
) -> None:
    grant_permission(verified_user, "notification.view_own")
    for i in range(3):
        notify(
            recipient=verified_user,
            kind="allocation.new",
            title=str(i),
            body="x",
            target_id=f"id-{i}",
        )
    client.force_authenticate(verified_user)

    response = client.post(reverse("notifications:notification-mark-all-read"))
    assert response.status_code == 200
    assert response.json() == {"updated": 3}

    assert Notification.objects.filter(recipient=verified_user, is_read=False).count() == 0


def test_unread_count_endpoint(
    client: APIClient, verified_user, grant_permission
) -> None:
    grant_permission(verified_user, "notification.view_own")
    client.force_authenticate(verified_user)

    # Empty.
    response = client.get(reverse("notifications:notification-unread-count"))
    assert response.status_code == 200
    assert response.json() == {"count": 0}

    # Add two.
    notify(recipient=verified_user, kind="allocation.new", title="A", body="a", target_id="u1")
    notify(recipient=verified_user, kind="allocation.new", title="B", body="b", target_id="u2")
    response = client.get(reverse("notifications:notification-unread-count"))
    assert response.json() == {"count": 2}

    # Mark all read.
    client.post(reverse("notifications:notification-mark-all-read"))
    response = client.get(reverse("notifications:notification-unread-count"))
    assert response.json() == {"count": 0}


def test_other_user_cannot_mark_someone_elses_notification(
    client: APIClient, verified_user, student_user, grant_permission
) -> None:
    grant_permission(verified_user, "notification.view_own")
    grant_permission(student_user, "notification.view_own")
    notif = notify(
        recipient=verified_user,
        kind="allocation.new",
        title="A",
        body="a",
        target_id="private",
    )
    client.force_authenticate(student_user)
    response = client.post(
        reverse("notifications:notification-mark-read", args=[notif.id])
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Integration: reassign fires notifications
# ---------------------------------------------------------------------------
def test_reassign_fires_notification(
    client: APIClient,
    verified_user,
    second_invigilator_user,
    officer_user,
    grant_permission,
    allocation,
) -> None:
    """The reassign action fires two notifications:
    * the *old* invigilator (verified_user) — handled in the view,
    * the *new* invigilator (second_invigilator_user) — handled by the
      post_save signal on Allocation.
    """
    # The officer has allocator.reassign to perform the swap.
    grant_permission(
        officer_user,
        "notification.view_own",
        "allocator.reassign",
        "allocator.run",
    )
    client.force_authenticate(officer_user)

    response = client.post(
        reverse("allocations:allocation-reassign", args=[allocation.id]),
        {"invigilator_id": str(second_invigilator_user.invigilator_profile.id)},
        format="json",
    )
    assert response.status_code == 200, response.json()

    # Old invigilator: one notification.
    old = Notification.objects.filter(
        recipient=verified_user, kind="allocation.reassigned"
    )
    assert old.count() == 1
    assert str(allocation.id) in old.first().target_id

    # New invigilator: one notification (the signal fires once on
    # the post_save with update_fields containing "invigilator").
    new = Notification.objects.filter(
        recipient=second_invigilator_user, kind="allocation.reassigned"
    )
    assert new.count() == 1


# ---------------------------------------------------------------------------
# Email delivery
# ---------------------------------------------------------------------------
def test_notify_sends_email_when_recipient_has_address(
    client: APIClient, verified_user, grant_permission
) -> None:
    """In EAGER mode the Celery task runs inline, so the email
    ends up in ``mail.outbox`` (the locmem backend)."""
    grant_permission(verified_user, "notification.view_own")
    notify(
        recipient=verified_user,
        kind="allocation.new",
        title="Test",
        body="Hello",
    )
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert "Test" in msg.subject
    assert verified_user.email in msg.to
    assert "Hello" in msg.body
