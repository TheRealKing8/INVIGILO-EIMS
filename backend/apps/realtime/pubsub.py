"""In-process pub/sub for SSE consumers (Phase 20).

The :class:`PubSub` object is a module-level singleton — every gunicorn
worker has one. When something interesting happens (a Notification is
created, a CheckIn lands) we call :meth:`PubSub.publish` with a channel
name; the SSE consumer coroutine in the *same* process is woken up.

TODO Phase 27+: swap in-process pubsub for redis.asyncio.pubsub when we
move to multi-worker gunicorn. Today the backend service in
docker-compose.yml runs ``-w 1`` (matching Render's single-dyno free
tier); with -w 2, a Notification saved in worker A would never wake a
subscriber in worker B. The Redis swap is scoped: replace the
``_subs`` dict + ``_loop`` background thread with a redis.asyncio.pubsub
``PubSub`` channel per ``user:<id>`` / ``session:<id>`` namespace. The
public surface (``publish`` / ``subscribe`` / ``unsubscribe``) stays
the same.

Channels are namespaced strings:

  * ``user:<user_id>`` — per-user wakes (the topbar bell).
  * ``session:<session_uuid>`` — per-session wakes (the live feed).

Why this isn't sse-starlette's ``SsePubSub``
--------------------------------------------
sse-starlette v2.1.3 doesn't ship a pubsub helper — only
``EventSourceResponse`` and ``ServerSentEvent``. We keep the
fan-out ourselves with a ``dict[str, list[asyncio.Queue]]`` of
subscribers per channel.

Loop ownership
--------------
The trick is that ``asyncio.Queue`` is bound to the loop it was
created in. ``publish`` can be called from a sync signal handler
*or* from inside the consumer's coroutine; both must deliver.

To make this work, we run a single persistent event loop on a
dedicated background thread (started lazily on first
``subscribe``). All queues are created on that loop. Publish
schedules ``put_nowait`` via ``loop.call_soon_threadsafe`` from
any other thread. The loop runs until process exit.

This is one more thread per worker (cheap; ~2 MB RSS) and
removes a class of "wrong-loop" bugs. The alternative —
``asyncio.run`` per publish — works for ``put_nowait`` but
fights with the consumer's loop, leading to ``RuntimeError`` on
the cross-loop queue call.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Iterable

logger = logging.getLogger("invigilo.realtime.pubsub")


class PubSub:
    """Module-level pub/sub keyed by channel name.

    ``publish`` is **synchronous** and thread-safe: it schedules
    ``queue.put_nowait`` on a single background loop. This is
    what the signal receivers in :mod:`apps.realtime.hooks` call
    from Django's sync ORM ``post_save`` path.

    ``subscribe`` is **async** and returns an ``asyncio.Queue``.
    The caller is expected to ``await queue.get()`` and call
    ``unsubscribe(channel, queue)`` when done.

    ``shutdown`` is called from the worker shutdown handler; it
    stops the background loop cleanly. Tests don't need to
    call it.
    """

    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue[str]]] = {}
        self._lock = threading.Lock()  # protects _subs list mutations
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------
    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        """Start the background loop on first use.

        Idempotent: subsequent calls return the same loop. The
        thread is a daemon so it doesn't block process exit.
        """
        if self._loop is not None and not self._loop.is_closed():
            return self._loop
        with self._lock:
            if self._loop is not None and not self._loop.is_closed():
                return self._loop
            loop = asyncio.new_event_loop()
            t = threading.Thread(
                target=_run_loop_forever,
                args=(loop,),
                name="invigilo-realtime-pubsub",
                daemon=True,
            )
            t.start()
            self._loop = loop
            self._thread = t
            logger.info("realtime.pubsub background loop started")
            return loop

    # ------------------------------------------------------------------
    # Sync side (called from signal handlers, no running loop assumed)
    # ------------------------------------------------------------------
    def publish(self, channel: str, event: str = "ping", data: Any = None) -> None:
        """Wake every consumer subscribed to ``channel`` on this process.

        ``event`` is the SSE event name (e.g. ``"unread_count"``).
        ``data`` is the event payload — typically ``None`` because
        the consumer re-fetches from the DB on wake. We only put
        the event *name* on the queue; the consumer knows the
        data shape from the channel.

        Failures are swallowed at DEBUG level — a missed wakeup
        is recovered by the 30s safety poll.
        """
        try:
            loop = self._ensure_loop()
            with self._lock:
                queues = list(self._subs.get(channel, ()))
            for q in queues:
                try:
                    loop.call_soon_threadsafe(q.put_nowait, event)
                except RuntimeError:
                    # Loop closed or queue full — drop the wakeup.
                    pass
        except Exception:  # noqa: BLE001
            # Never let a publish failure bubble up and 500 the API
            # call that triggered it. SSE is a best-effort wakeup.
            logger.debug("realtime.publish failed for channel=%s", channel, exc_info=True)
        else:
            logger.debug("realtime.publish channel=%s event=%s", channel, event)

    # ------------------------------------------------------------------
    # Async side (called from the SSE consumer on the consumer's loop)
    # ------------------------------------------------------------------
    async def subscribe(self, channel: str) -> asyncio.Queue[str]:
        """Register a fresh queue on ``channel`` and return it.

        The queue is created on the *background* loop so
        ``publish`` (from any thread) can deliver to it without
        cross-loop issues. The consumer calls ``queue.get()``,
        which transparently hops to the background loop.

        The caller is expected to ``await queue.get()`` and to
        call :meth:`unsubscribe` when its stream ends.
        """
        loop = self._ensure_loop()
        # We need a queue bound to the background loop. Build it
        # via ``call_soon_threadsafe`` and await the result with
        # an asyncio.Future. The simpler alternative
        # (``asyncio.Queue`` on the consumer's loop) breaks
        # ``publish`` from other threads.
        future: asyncio.Future[asyncio.Queue[str]] = asyncio.Future()

        def _make_queue() -> None:
            try:
                q: asyncio.Queue[str] = asyncio.Queue(maxsize=64)
                # asyncio.Queue is loop-bound; this runs on the
                # background loop so its loop IS the background loop.
                with self._lock:
                    self._subs.setdefault(channel, []).append(q)
                loop.call_soon_threadsafe(future.set_result, q)
            except Exception as exc:  # pragma: no cover — defensive
                loop.call_soon_threadsafe(future.set_exception, exc)

        loop.call_soon_threadsafe(_make_queue)
        return await future

    async def unsubscribe(self, channel: str, queue: asyncio.Queue[str]) -> None:
        """Remove ``queue`` from the channel's subscriber list.

        Safe to call even if the channel is empty and even if
        the queue was already removed by a previous unsubscribe.
        """
        with self._lock:
            subs = self._subs.get(channel)
            if subs and queue in subs:
                subs.remove(queue)
                if not subs:
                    self._subs.pop(channel, None)

    # ------------------------------------------------------------------
    # Introspection (tests + ops)
    # ------------------------------------------------------------------
    def subscriber_count(self, channel: str) -> int:
        """Number of live subscribers on ``channel`` on this process."""
        with self._lock:
            return len(self._subs.get(channel, ()))

    def channels(self) -> Iterable[str]:
        """All channels with at least one subscriber right now."""
        with self._lock:
            return tuple(self._subs.keys())

    def shutdown(self) -> None:  # pragma: no cover — process exit
        """Stop the background loop. Called from worker shutdown."""
        with self._lock:
            loop = self._loop
            self._loop = None
            self._thread = None
        if loop and not loop.is_closed():
            loop.call_soon_threadsafe(loop.stop)


def _run_loop_forever(loop: asyncio.AbstractEventLoop) -> None:
    """Target for the background thread. Runs ``loop`` until stopped."""
    asyncio.set_event_loop(loop)
    try:
        loop.run_forever()
    finally:
        try:
            loop.close()
        except Exception:  # noqa: BLE001
            pass


# Module-level singleton. Every gunicorn worker has one.
pubsub = PubSub()


def channel_for_user(user_id: Any) -> str:
    return f"user:{user_id}"


def channel_for_session(session_id: Any) -> str:
    return f"session:{session_id}"


# Keep the legacy name; ``hooks.py`` and ``views.py`` import this.
def publish(channel: str, event: str = "ping", data: Any = None) -> None:
    """Functional wrapper around :meth:`PubSub.publish`.

    Kept as a module-level helper so call sites can do
    ``from apps.realtime.pubsub import publish`` without going
    through the singleton.
    """
    pubsub.publish(channel, event, data)


__all__ = [
    "PubSub",
    "pubsub",
    "publish",
    "channel_for_user",
    "channel_for_session",
]
