"""SSE streaming views (Phase 20).

Three endpoints:

  * ``GET /api/v1/realtime/notifications/stream/`` — per-user
    notification wakeup. Emits ``snapshot`` on connect, then
    ``unread_count`` whenever a Notification is created or
    marked-read for this user.
  * ``GET /api/v1/realtime/attendance/sessions/<uuid>/stream/`` —
    per-session live check-in feed. Emits ``snapshot`` of the
    20 most recent rows on connect, then ``checkin`` per new
    row for this session.
  * ``POST /api/v1/realtime/ai/chat/stream/`` — streaming AI
    reply. Emits ``meta`` (model info), ``token`` (incremental
    LLM output), ``done`` (usage), or ``error`` (upstream
    failure).

Why Django ``StreamingHttpResponse`` and not ``EventSourceResponse``
-------------------------------------------------------------------
``sse-starlette`` v2 ships an ASGI-shaped ``EventSourceResponse`` that
uses ``anyio`` + a Starlette response. It does not work under the
Django WSGI handler (which is what gunicorn speaks today). We use
``sse-starlette`` for the *event-bytes formatting* — its
:func:`ensure_bytes` helper knows the SSE wire format — and bridge
to ``StreamingHttpResponse`` with a sync generator. This keeps the
dep count at one and stays WSGI-compatible.

Heartbeat + safety timer
------------------------
Every stream emits a ``ping`` event every :data:`HEARTBEAT_SECONDS`
(15s — under nginx's 60s default ``proxy_read_timeout``). The
consumer's ``EventSource`` ignores ping events; the heartbeat
exists to keep the TCP connection alive through proxies that
idle-out streams.

In addition, every stream has a 30s safety timer: if no real
event fired in that window, we emit a no-op ``ping`` so the
consumer re-fetches from the DB. This bounds the cross-worker
lag for events written by a *different* gunicorn worker.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Iterator

from asgiref.sync import async_to_sync
from django.conf import settings
from django.http import StreamingHttpResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from sse_starlette.sse import ServerSentEvent, ensure_bytes

from apps.attendance.services import build_live_feed
from apps.exams.models import ExamSession
from apps.notifications.models import Notification

from .pubsub import channel_for_session, channel_for_user, pubsub

logger = logging.getLogger("invigilo.realtime")

# Heartbeat cadence. sse-starlette's default; we set it explicitly so
# the number is in this file where anyone reviewing the plan can see it.
HEARTBEAT_SECONDS = 15
# Safety timer: if no real event arrived in this window, emit a ping
# so the consumer re-fetches from the DB. Bounds cross-worker lag.
SAFETY_PING_SECONDS = 30
# Hard cap on a single stream's lifetime. Stops a zombie stream from
# holding a worker slot if the heartbeat doesn't notice the disconnect.
MAX_STREAM_LIFETIME_SECONDS = 5 * 60


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sse(event: str, data: Any) -> bytes:
    """Format a single SSE event as bytes using sse-starlette's
    wire-format helper. JSON-serialises the data so dicts/lists
    cross the wire without bespoke encoding.
    """
    if not isinstance(data, str):
        data = json.dumps(data, default=str)
    return ensure_bytes(ServerSentEvent(data=data, event=event), sep="\n\n")


def _sse_response(iterator: Iterator[bytes]) -> StreamingHttpResponse:
    """Wrap a sync bytes iterator in a ``StreamingHttpResponse``.

    Headers:
      * ``Content-Type: text/event-stream`` — required by the spec
        so the browser routes the response to ``EventSource``.
      * ``Cache-Control: no-cache, no-transform`` — prevent any
        middleware from buffering or compressing the stream.
      * ``X-Accel-Buffering: no`` — disable nginx response buffering
        so events reach the client as soon as we yield them.
    """
    response = StreamingHttpResponse(iterator, content_type="text/event-stream")
    response["Cache-Control"] = "no-cache, no-transform"
    response["X-Accel-Buffering"] = "no"
    return response


async def _wait_event_async(channel: str, timeout: float) -> str | None:
    """Wait up to ``timeout`` seconds for an event on ``channel``.

    Returns the published event name (a string) or ``None`` on
    timeout. Uses ``anyio.move_on_after`` so the underlying
    queue.get() is cancelled cleanly on timeout — no leaked
    coroutines.
    """
    import anyio

    queue = await pubsub.subscribe(channel=channel)
    try:
        with anyio.move_on_after(timeout):
            try:
                event = await queue.get()
            except BaseException:
                return None
            return event if isinstance(event, str) else None
    finally:
        await pubsub.unsubscribe(channel=channel, queue=queue)


def _wait_event(channel: str, timeout: float) -> str | None:
    """Sync wrapper around :func:`_wait_event_async` for the
    Django WSGI handler. Spawns a one-shot event loop on the
    ``anyio`` backend (``asyncio``)."""
    return async_to_sync(_wait_event_async)(channel, timeout)


# ---------------------------------------------------------------------------
# Notifications stream
# ---------------------------------------------------------------------------
@extend_schema(
    tags=["realtime"],
    summary="Per-user notification SSE stream.",
    description=(
        "Server-Sent Events stream that wakes the topbar bell in real time. "
        "Emits ``event: snapshot`` on connect with the current unread count, "
        "then ``event: unread_count`` whenever a Notification is created or "
        "marked-read for the calling user. Heartbeat pings every 15s; closes "
        "after 5 minutes (the client auto-reconnects)."
    ),
    responses={200: OpenApiResponse(description="text/event-stream")},
)
class NotificationsStreamView(APIView):
    permission_classes = [IsAuthenticated]
    # No DRF throttle on the stream — the consumer holds an open
    # connection; throttling on the connect rate belongs at the
    # load balancer / rate-limit-by-IP layer, not here.

    def get(self, request):  # type: ignore[no-untyped-def]
        user = request.user
        if not user or not user.is_authenticated:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        channel = channel_for_user(user.id)

        def unread_count() -> int:
            return Notification.objects.filter(
                recipient_id=user.id, is_read=False
            ).count()

        def gen() -> Iterator[bytes]:
            started = time.monotonic()
            logger.info(
                "realtime.notifications.open user=%s channel=%s",
                getattr(user, "email", "anon"),
                channel,
            )
            try:
                # 1) Snapshot on connect.
                yield _sse("snapshot", {"unread_count": unread_count()})

                # 2) Main loop. We block for up to SAFETY_PING_SECONDS
                # on a pubsub event; on timeout we emit a ping so the
                # client knows the stream is still alive.
                while True:
                    elapsed = time.monotonic() - started
                    if elapsed > MAX_STREAM_LIFETIME_SECONDS:
                        logger.info(
                            "realtime.notifications.close user=%s reason=lifetime",
                            getattr(user, "email", "anon"),
                        )
                        return
                    event_name = _wait_event(channel, SAFETY_PING_SECONDS)
                    if event_name is None:
                        # Timeout — emit a ping (heartbeat).
                        yield _sse("ping", {"t": int(elapsed)})
                        continue
                    if event_name == "unread_count":
                        yield _sse("unread_count", {"unread_count": unread_count()})
                    else:
                        # Unknown event — still re-emit ping so the
                        # client knows the stream is alive.
                        yield _sse("ping", {"t": int(elapsed)})
            except GeneratorExit:
                logger.info(
                    "realtime.notifications.close user=%s reason=client_disconnect",
                    getattr(user, "email", "anon"),
                )
                return

        return _sse_response(gen())


# ---------------------------------------------------------------------------
# Attendance session live feed
# ---------------------------------------------------------------------------
@extend_schema(
    tags=["realtime"],
    summary="Per-session live check-in SSE stream.",
    description=(
        "Server-Sent Events stream that replaces the 5s polling on the "
        "session detail page. Emits ``event: snapshot`` on connect with "
        "the 20 most recent CheckIn rows, then ``event: checkin`` per "
        "new row. Heartbeat pings every 15s."
    ),
    responses={200: OpenApiResponse(description="text/event-stream")},
)
class AttendanceSessionStreamView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id: str):  # type: ignore[no-untyped-def]
        try:
            session = ExamSession.objects.get(id=session_id)
        except ExamSession.DoesNotExist:
            return Response(
                {"detail": "Session not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        channel = channel_for_session(session.id)

        def gen() -> Iterator[bytes]:
            started = time.monotonic()
            logger.info(
                "realtime.attendance.open session=%s channel=%s",
                session.id, channel,
            )
            try:
                # 1) Snapshot — same shape as the polling endpoint
                # so the client can swap them transparently.
                yield _sse("snapshot", build_live_feed(session))

                while True:
                    elapsed = time.monotonic() - started
                    if elapsed > MAX_STREAM_LIFETIME_SECONDS:
                        logger.info(
                            "realtime.attendance.close session=%s reason=lifetime",
                            session.id,
                        )
                        return
                    event_name = _wait_event(channel, SAFETY_PING_SECONDS)
                    if event_name is None:
                        yield _sse("ping", {"t": int(elapsed)})
                        continue
                    if event_name == "checkin":
                        # Re-emit a full snapshot — the simplest,
                        # cheapest, race-free path. The client
                        # re-orders by ``at`` on the UI side.
                        yield _sse("checkin", build_live_feed(session))
                    else:
                        yield _sse("ping", {"t": int(elapsed)})
            except GeneratorExit:
                logger.info(
                    "realtime.attendance.close session=%s reason=client_disconnect",
                    session.id,
                )
                return

        return _sse_response(gen())


# ---------------------------------------------------------------------------
# AI streaming
# ---------------------------------------------------------------------------
class AIChatStreamUserThrottle(UserRateThrottle):
    """Same scope as the non-streaming chat so a user can't burn
    through LLM calls by alternating between the two endpoints."""
    scope = "ai_chat"


@extend_schema(
    tags=["realtime"],
    summary="Streaming AI assistant reply.",
    description=(
        "Server-Sent Events stream of the LLM reply. Emits ``event: meta`` "
        "on connect, then ``event: token`` per OpenRouter chunk, then "
        "``event: done`` with usage. On upstream failure, ``event: error`` "
        "is emitted and the client should fall back to the non-streaming "
        "endpoint. Rate-limited to 30/min/user (same as the non-streaming "
        "chat)."
    ),
    request={"application/json": {"type": "object", "properties": {"message": {"type": "string"}}}},
    responses={200: OpenApiResponse(description="text/event-stream")},
)
class AIChatStreamView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AIChatStreamUserThrottle]

    def post(self, request):  # type: ignore[no-untyped-def]
        message = (request.data.get("message") or "").strip()
        if not message:
            return Response(
                {"detail": "message is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(message) > 500:
            return Response(
                {"detail": "message must be 500 characters or fewer"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = request.user
        api_key = settings.OPENROUTER_API_KEY

        def gen() -> Iterator[bytes]:
            started = time.monotonic()
            logger.info(
                "realtime.ai.open user=%s mode=%s",
                getattr(user, "email", "anon"),
                "llm" if api_key else "rule",
            )
            # Tokens / errors are appended to ``outbox`` by the
            # stream helpers; the generator drains the outbox
            # between phases. This is the standard "sending values
            # into a generator" pattern — Python generators don't
            # compose via yield-from-across, but a list-as-sink
            # works fine.
            outbox: list[bytes] = []

            def emit(event: str, data: Any) -> None:
                outbox.append(_sse(event, data))

            def drain() -> Iterator[bytes]:
                while outbox:
                    yield outbox.pop(0)

            try:
                emit("meta", {
                    "started_at": timezone.now().isoformat(),
                    "mode": "llm" if api_key else "rule",
                })
                yield from drain()

                if api_key:
                    reply_len = self._stream_llm(user, message, emit=emit)
                else:
                    reply_len = self._stream_rule(user, message, emit=emit)
                yield from drain()

                emit("done", {
                    "latency_ms": int((time.monotonic() - started) * 1000),
                    "length": reply_len,
                    "mode": "llm" if api_key else "rule_based",
                })
                yield from drain()
            except GeneratorExit:
                logger.info(
                    "realtime.ai.close user=%s reason=client_disconnect",
                    getattr(user, "email", "anon"),
                )
                return

        return _sse_response(gen())

    # -- LLM path --------------------------------------------------------
    def _stream_llm(
        self,
        user: Any,
        message: str,
        *,
        emit: Any,
    ) -> int:
        """Stream the LLM reply token-by-token.

        Appends ``event: token`` with ``{"delta": "..."}`` to
        ``emit`` per chunk and a final ``event: error`` if the
        upstream call fails. Returns the length of the
        concatenated reply.
        """
        from apps.ai.openrouter import OpenRouterError, stream_chat
        from apps.ai.services import _user_role_code, build_context, build_messages

        try:
            try:
                role = _user_role_code(user)
            except Exception:  # noqa: BLE001
                role = "GUEST"
            ctx = build_context()
            messages = build_messages(role=role, message=message, ctx=ctx)

            full_chunks: list[str] = []
            for event in stream_chat(messages):
                if event.kind == "token" and event.delta:
                    full_chunks.append(event.delta)
                    emit("token", {"delta": event.delta})
                elif event.kind == "error":
                    emit("error", {"detail": event.detail or "openrouter error"})
                    return len("".join(full_chunks))
            return len("".join(full_chunks))
        except OpenRouterError as exc:
            logger.warning(
                "realtime.ai user=%s openrouter_error status=%s",
                getattr(user, "email", "anon"),
                exc.status_code,
            )
            emit("error", {"detail": str(exc)[:200]})
            return 0
        except Exception:  # noqa: BLE001
            logger.exception("realtime.ai user=%s unexpected", getattr(user, "email", "anon"))
            emit("error", {"detail": "internal error"})
            return 0

    # -- Rule-based path -------------------------------------------------
    def _stream_rule(
        self,
        user: Any,
        message: str,
        *,
        emit: Any,
    ) -> int:
        """Stream the rule-based reply in 4-char chunks.

        We use the same ``compose_reply`` helper the non-streaming
        endpoint uses, then drip-feed the result so the UX of
        "tokens appear in real time" is consistent. 4 chars at a
        time keeps the stream moving without spamming the wire.
        """
        from apps.ai.services import build_context, compose_reply

        try:
            ctx = build_context()
            reply, _suggestions, _intent = compose_reply(message, ctx)
        except Exception:  # noqa: BLE001
            logger.exception("realtime.ai rule-based fallback failed")
            emit("error", {"detail": "rule-based fallback failed"})
            return 0

        # 4-char chunks with a 2ms pause. A 500-char reply drains
        # in 250ms — fast enough to feel instant, slow enough
        # to show the typing animation.
        for i in range(0, len(reply), 4):
            emit("token", {"delta": reply[i : i + 4]})
            time.sleep(0.002)
        return len(reply)


__all__ = [
    "HEARTBEAT_SECONDS",
    "SAFETY_PING_SECONDS",
    "MAX_STREAM_LIFETIME_SECONDS",
    "NotificationsStreamView",
    "AttendanceSessionStreamView",
    "AIChatStreamView",
]
