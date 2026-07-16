"""SSE stream tests (Phase 20).

We exercise the three new endpoints end-to-end with the test client.
The notifications and attendance streams assert against the wire
format (``event: snapshot``, ``data: {...}``) and the side effect
(a saved row produces a wakeup). The AI stream asserts the
``meta`` / ``token`` / ``done`` event sequence in rule-based mode
(no OpenRouter key) and the error path in LLM mode (mocked).

The tests stay synchronous: Django's test client doesn't have a
native async story, but our SSE views are sync generators wrapped
in :class:`StreamingHttpResponse` — so we just read
``response.streaming_content`` to a chunked ``bytes`` blob and
parse the events from that. The 30s safety poll would make this
test slow if we let the stream run forever, so each test reads a
bounded prefix of the stream and then closes the response.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import Role, UserRole
from apps.exams.models import ExamSession


User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_student(email: str = "sse-student@gmail.com"):
    """A STUDENT user we can force-authenticate on the test client.

    Avoids the OTP + cookie flow so the SSE tests stay focused on
    the stream wire format. Mirrors the conftest fixture pattern
    from sibling apps.
    """
    role, _ = Role.objects.update_or_create(
        code="STUDENT", defaults={"name": "Student", "is_active": True}
    )
    user = User.objects.create_user(
        email=email,
        full_name="SSE Student",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=role)
    return user


def _login(api_client: APIClient):
    user = _make_student()
    api_client.force_authenticate(user=user)
    return user


def _drain_sse(response, *, max_bytes: int = 4096, max_chunks: int = 8) -> str:
    """Pull a bounded prefix of an SSE response and return the wire text.

    We iterate the streaming_content iterable but break out the
    moment we have enough events for the assertion. The response
    stays open under the WSGI handler, but the test client's
    streaming content iterator is a normal Python generator, so
    closing it is just a matter of breaking the loop.
    """
    body = bytearray()
    chunks = 0
    for chunk in response.streaming_content:
        if not chunk:
            continue
        body.extend(chunk)
        chunks += 1
        if len(body) >= max_bytes or chunks >= max_chunks:
            break
    # Force-close the underlying response so the generator's
    # GeneratorExit handler runs and the DB connection releases.
    if hasattr(response, "close"):
        try:
            response.close()
        except Exception:  # noqa: BLE001
            pass
    return body.decode("utf-8", errors="replace")


def _parse_events(wire: str) -> list[tuple[str, dict]]:
    """Parse SSE wire text into ``[(event_name, data_dict), ...]``.

    Skips ``ping`` events — they're heartbeats, not signal
    evidence — and ignores anything without a ``data:`` payload.
    """
    events: list[tuple[str, dict]] = []
    current_event = "message"  # SSE default
    data_lines: list[str] = []
    for line in wire.splitlines():
        if not line:
            if data_lines:
                try:
                    payload = json.loads("\n".join(data_lines))
                except ValueError:
                    payload = {"raw": "\n".join(data_lines)}
                if current_event != "ping":
                    events.append((current_event, payload))
                current_event = "message"
                data_lines = []
            continue
        if line.startswith(":"):
            # SSE comment line — skip.
            continue
        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:"):].strip())
    return events


# ---------------------------------------------------------------------------
# Notifications stream
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
class TestNotificationsStream:
    def test_snapshot_on_connect(self):
        """On connect, the stream sends ``event: snapshot`` with the
        current unread count for the calling user."""
        api = APIClient()
        _login(api)
        response = api.get("/api/v1/realtime/notifications/stream/")
        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/event-stream")
        wire = _drain_sse(response)
        events = _parse_events(wire)
        assert events, f"no events parsed from: {wire!r}"
        assert events[0][0] == "snapshot"
        assert events[0][1]["unread_count"] == 0

    def test_unread_count_event_after_create(self):
        """A new Notification fires ``event: unread_count`` on the
        open stream with the new count."""
        api = APIClient()
        user = _login(api)
        from apps.notifications.services import notify

        # Open the stream. The snapshot event lands immediately.
        response = api.get("/api/v1/realtime/notifications/stream/")
        assert response.status_code == 200
        # Read the snapshot off the wire so the consumer is now
        # blocked on the pubsub queue.
        first = next(iter(response.streaming_content))
        assert b"event: snapshot" in first

        # Trigger a notification for *this* user. The post_save
        # signal publishes to the user channel; the stream
        # generator wakes and yields an unread_count event.
        notify(
            recipient=user,
            kind="allocation.updated",
            title="SSE smoke",
            body="wake up",
        )

        # Drain a few more chunks; the unread_count event should
        # be among them.
        body = bytearray(first)
        for _ in range(6):
            try:
                chunk = next(iter(response.streaming_content))
            except StopIteration:
                break
            body.extend(chunk)
        response.close()

        wire = body.decode("utf-8", errors="replace")
        events = _parse_events(wire)
        names = [name for name, _ in events]
        assert "unread_count" in names, f"no unread_count in {wire!r}"
        # Find the first unread_count event and check it bumped
        # the count to 1.
        for name, data in events:
            if name == "unread_count":
                assert data["unread_count"] == 1
                break

    def test_requires_auth(self):
        """Anonymous connections are rejected before the stream opens."""
        api = APIClient()
        response = api.get("/api/v1/realtime/notifications/stream/")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Attendance session stream
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
class TestAttendanceStream:
    def _make_session(self) -> ExamSession:
        """Bare ExamSession with all required FKs.

        Mirrors ``apps/attendance/tests/test_scan.py::session`` —
        the minimum scaffolding to satisfy the FK constraints
        without invoking the full factory or the engine.
        """
        from apps.academic.models import Course, Department, Faculty, Program
        from apps.exams.models import ExamPeriod
        from apps.rooms.models import Building, Room

        f = Faculty.objects.create(code="F", name="F")
        d = Department.objects.create(faculty=f, code="D", name="D")
        p = Program.objects.create(department=d, code="P", name="P")
        course = Course.objects.create(program=p, code="C", title="C", credit_hours=3)
        building = Building.objects.create(code="B", name="B")
        room = Room.objects.create(building=building, code="R", capacity=100)
        period = ExamPeriod.objects.create(
            code="T1", name="T1",
            starts_on="2026-08-01", ends_on="2026-08-30",
        )
        return ExamSession.objects.create(
            period=period, course=course, room=room,
            starts_at="2026-08-15T09:00:00Z", ends_at="2026-08-15T11:00:00Z",
            capacity=100, registered=80, invigilators_required=1, status="scheduled",
        )

    def test_snapshot_on_connect(self):
        """On connect, the stream sends ``event: snapshot`` with the
        live feed for the session (0 entries on a fresh session)."""
        api = APIClient()
        _login(api)
        session = self._make_session()
        response = api.get(
            f"/api/v1/realtime/attendance/sessions/{session.id}/stream/"
        )
        assert response.status_code == 200
        wire = _drain_sse(response)
        events = _parse_events(wire)
        assert events, f"no events parsed from: {wire!r}"
        assert events[0][0] == "snapshot"
        # ``build_live_feed`` returns ``{"entries": [...]}`` — see
        # Phase 19. We don't pin the full shape, just the contract.
        assert "entries" in events[0][1]

    def test_checkin_event_after_create(self):
        """A new CheckIn for the session fires ``event: checkin`` with
        a refreshed live-feed snapshot."""
        api = APIClient()
        invigilator = _make_student(email="inv@x.com")
        # The user is the recorder; the invigilator can be self.
        api.force_authenticate(user=invigilator)
        session = self._make_session()

        response = api.get(
            f"/api/v1/realtime/attendance/sessions/{session.id}/stream/"
        )
        assert response.status_code == 200
        first = next(iter(response.streaming_content))
        assert b"event: snapshot" in first

        # Land a check-in for the session. We need the invigilator
        # to have a profile so the FK satisfies.
        from apps.invigilators.models import InvigilatorProfile

        profile, _ = InvigilatorProfile.objects.get_or_create(user=invigilator)
        from apps.attendance.models import CheckIn

        CheckIn.objects.create(
            session=session,
            user=invigilator,
            kind="invigilator",
            method="self",
            recorded_by=invigilator,
        )

        body = bytearray(first)
        for _ in range(6):
            try:
                chunk = next(iter(response.streaming_content))
            except StopIteration:
                break
            body.extend(chunk)
        response.close()

        wire = body.decode("utf-8", errors="replace")
        events = _parse_events(wire)
        names = [name for name, _ in events]
        assert "checkin" in names, f"no checkin in {wire!r}"

    def test_404_for_missing_session(self):
        """A non-existent session UUID returns 404, not a stream."""
        api = APIClient()
        _login(api)
        response = api.get(
            "/api/v1/realtime/attendance/sessions/"
            "00000000-0000-0000-0000-000000000000/stream/"
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# AI chat stream
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
class TestAIChatStream:
    def test_rule_based_stream(self):
        """With no OPENROUTER_API_KEY the stream emits meta + token*
        + done events in rule-based mode."""
        api = APIClient()
        _login(api)
        with patch("apps.realtime.views.settings") as fake_settings:
            # Empty key → rule path.
            fake_settings.OPENROUTER_API_KEY = ""
            response = api.post(
                "/api/v1/realtime/ai/chat/stream/",
                data={"message": "what's happening today?"},
                format="json",
            )
        assert response.status_code == 200
        wire = _drain_sse(response, max_bytes=8192, max_chunks=16)
        events = _parse_events(wire)
        names = [n for n, _ in events]
        # meta is the first event; the rule reply streams as
        # multiple token events; done is the terminator.
        assert "meta" in names
        assert "token" in names
        assert "done" in names
        # The done event carries the length + mode metadata.
        for n, data in events:
            if n == "done":
                assert data["mode"] == "rule_based"
                assert data["length"] > 0
                break

    def test_empty_message_rejected(self):
        """Empty message is a 400 — same contract as the non-streaming
        endpoint so the client can fall back cleanly."""
        api = APIClient()
        _login(api)
        response = api.post(
            "/api/v1/realtime/ai/chat/stream/",
            data={"message": ""},
            format="json",
        )
        assert response.status_code == 400

    def test_llm_error_event(self):
        """When the LLM raises an OpenRouterError we emit an
        ``event: error`` and the stream ends with done."""
        api = APIClient()
        _login(api)

        from apps.ai.openrouter import LLMToken

        async def fake_stream_chat(messages):
            yield LLMToken(kind="error", detail="openrouter 503: upstream")

        with patch("apps.realtime.views.settings") as fake_settings, \
             patch("apps.ai.openrouter.stream_chat", side_effect=fake_stream_chat):
            fake_settings.OPENROUTER_API_KEY = "test-key"
            response = api.post(
                "/api/v1/realtime/ai/chat/stream/",
                data={"message": "hi"},
                format="json",
            )
        assert response.status_code == 200
        wire = _drain_sse(response, max_bytes=4096, max_chunks=8)
        events = _parse_events(wire)
        names = [n for n, _ in events]
        assert "error" in names
        # Done still fires (the client uses it to know the stream
        # is finished even on error).
        assert "done" in names


# ---------------------------------------------------------------------------
# Pubsub unit
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestPubSub:
    def test_publish_wakes_subscriber(self):
        """A subscriber on a channel receives a published event name."""
        import asyncio

        from apps.realtime.pubsub import (
            channel_for_user,
            pubsub,
        )

        async def scenario() -> str:
            channel = channel_for_user("test-user-1")
            queue = await pubsub.subscribe(channel=channel)
            try:
                # Publish from a different code path (the
                # signal handler does this synchronously).
                pubsub.publish(channel, event="unread_count")
                # Give the call_soon_threadsafe callback a tick
                # to run.
                for _ in range(10):
                    try:
                        return await asyncio.wait_for(queue.get(), timeout=0.05)
                    except asyncio.TimeoutError:
                        continue
                return ""
            finally:
                await pubsub.unsubscribe(channel=channel, queue=queue)

        result = asyncio.run(scenario())
        assert result == "unread_count"

    def test_unsubscribed_queue_does_not_receive(self):
        """After unsubscribe, publishes to the same channel don't
        deliver to a removed queue."""
        import asyncio

        from apps.realtime.pubsub import (
            channel_for_session,
            pubsub,
        )

        async def scenario() -> int:
            channel = channel_for_session("sess-x")
            queue = await pubsub.subscribe(channel=channel)
            await pubsub.unsubscribe(channel=channel, queue=queue)
            pubsub.publish(channel, event="checkin")
            await asyncio.sleep(0.05)
            return queue.qsize()

        qsize = asyncio.run(scenario())
        assert qsize == 0
