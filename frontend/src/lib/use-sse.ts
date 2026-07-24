/**
 * useEventStream — a small Server-Sent Events client for the dashboard.
 *
 * The browser's native ``EventSource`` cannot set custom ``Authorization``
 * headers and cannot reliably send ``credentials: 'include'`` for
 * cross-origin streams. The dev env is cross-origin (Next.js on
 * ``localhost:3000`` → API on ``127.0.0.1:8000``) and even same-origin
 * in production needs the bearer header. We open the stream with a
 * plain ``fetch`` (which honors the same ``Authorization: Bearer``
 * plumbing the rest of ``@/lib/api`` uses) and parse the SSE wire
 * format from the response body. See
 * ``backend/apps/realtime/views.py::_sse`` for the server side and
 * ``apps/realtime/tests/test_streams.py::_parse_events`` for the
 * canonical wire-format reference.
 *
 * Wire format (per the SSE spec the server implements):
 *
 *     event: <name>\n
 *     data: <json>\n
 *     \n
 *
 * Blocks are separated by a blank line (``\n\n``). Multi-line data is
 * joined with ``\n`` by the spec, but the backend only ever emits a
 * single data line per event so we don't bother with that.
 *
 * The server has a hard 5-minute lifetime cap
 * (``MAX_STREAM_LIFETIME_SECONDS = 5 * 60`` in
 * ``backend/apps/realtime/views.py:76``). Reconnects are expected and
 * the client must not treat them as failures. We schedule a single
 * reconnect after a short jittered backoff (2s, then 5s, then 10s;
 * reset to 2s on a successful open).
 */
"use client";

import { useEffect, useRef, useState } from "react";

import { getStoredAccessToken } from "@/lib/api";

export type EventStreamStatus = "connecting" | "open" | "error" | "closed";

export type EventStreamHandlers<T> = {
  /**
   * Called on the very first event of every connection (the
   * ``snapshot`` event the server emits on connect). Use this for
   * the initial paint. ``data`` is the JSON-parsed ``data`` field.
   */
  onSnapshot?: (data: T) => void;
  /**
   * Called for every named event after ``snapshot``. The default
   * behaviour if you don't supply this is to drop everything except
   * ``ping`` (which the parser already drops for you).
   */
  onEvent?: (name: string, data: T) => void;
  /**
   * Called on a non-recoverable stream error. The hook will still
   * attempt a single reconnect after the backoff window.
   */
  onError?: (err: Error) => void;
};

export type EventStreamOptions = {
  /**
   * Optional list of event names to listen for. Anything not in the
   * list is dropped before reaching the callbacks (saves a JSON parse
   * per event). Defaults to all non-ping events.
   */
  listen?: string[];
};

const BACKOFF_STEPS_MS = [2_000, 5_000, 10_000] as const;

/**
 * Parse a single SSE block (``event: x\ndata: y``) into a name/data
 * pair. Returns ``null`` for a comment block (lines starting with
 * ``:``), for an empty block, or for a block whose ``data`` field
 * is missing. Multi-line ``data`` is joined with ``\n`` per the SSE
 * spec, but the backend only emits a single data line.
 */
function parseBlock(block: string): { name: string; data: string } | null {
  let name: string | null = null;
  const dataLines: string[] = [];
  for (const rawLine of block.split("\n")) {
    if (rawLine.length === 0 || rawLine.startsWith(":")) continue;
    const colon = rawLine.indexOf(":");
    if (colon === -1) continue;
    const field = rawLine.slice(0, colon);
    // The spec lets the first character after ``:`` be a single space;
    // strip it if present.
    const value = rawLine.slice(colon + 1).replace(/^ /, "");
    if (field === "event") {
      name = value;
    } else if (field === "data") {
      dataLines.push(value);
    }
  }
  if (name === null || dataLines.length === 0) return null;
  return { name, data: dataLines.join("\n") };
}

/**
 * Drive one open stream to completion. Resolves with ``"closed"`` on
 * a normal disconnect (e.g. the 5-minute server cap) or with
 * ``"error"`` if the fetch failed or the body reader errored. The
 * caller is responsible for deciding whether to reconnect.
 */
async function readStream(
  response: Response,
  handlers: {
    onSnapshot: ((data: unknown) => void) | undefined;
    onEvent: ((name: string, data: unknown) => void) | undefined;
    onError: ((err: Error) => void) | undefined;
    listen: Set<string> | null;
  },
  signal: AbortSignal,
): Promise<"closed" | "error"> {
  if (!response.body) {
    handlers.onError?.(new Error("Response has no body"));
    return "error";
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        // Normal end of stream. The server closes every 5 minutes;
        // we treat this as a clean shutdown so the caller can
        // reconnect without surfacing an error.
        if (buffer.length > 0) {
          const tail = parseBlock(buffer);
          if (tail && !tail.name.startsWith(":")) {
            dispatch(tail, handlers, listenFilter(handlers.listen));
          }
        }
        return "closed";
      }
      buffer += decoder.decode(value, { stream: true });
      // Split into blocks. The server emits ``\n\n`` between events;
      // we split on the *first* ``\n\n`` and keep any trailing
      // partial block in the buffer for the next chunk.
      const matches = listenFilter(handlers.listen);
      let split: number;
      while ((split = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, split);
        buffer = buffer.slice(split + 2);
        if (block.length === 0) continue;
        const parsed = parseBlock(block);
        if (!parsed) continue;
        if (parsed.name === "ping") continue;
        dispatch(
          { name: parsed.name, data: parsed.data },
          handlers,
          matches,
        );
      }
      // If the read was aborted mid-stream, surface as an error so
      // the caller's reconnect path skips the backoff.
      if (signal.aborted) return "error";
    }
  } catch (err) {
    if (signal.aborted) return "error";
    const wrapped = err instanceof Error ? err : new Error(String(err));
    handlers.onError?.(wrapped);
    return "error";
  } finally {
    try {
      reader.releaseLock();
    } catch {
      /* reader already released */
    }
  }
}

function listenFilter(
  listen: Set<string> | null,
): (name: string) => boolean {
  return listen ? (name) => listen.has(name) : () => true;
}

function dispatch(
  parsed: { name: string; data: string },
  handlers: {
    onSnapshot: ((data: unknown) => void) | undefined;
    onEvent: ((name: string, data: unknown) => void) | undefined;
  },
  matches: (name: string) => boolean,
): "snapshot" | "event" | "dropped" {
  if (!matches(parsed.name)) return "dropped";
  let payload: unknown;
  try {
    payload = JSON.parse(parsed.data);
  } catch {
    // Non-JSON data is dropped — the server only emits JSON, so this
    // is a protocol violation worth ignoring.
    return "dropped";
  }
  if (parsed.name === "snapshot") {
    handlers.onSnapshot?.(payload);
    return "snapshot";
  }
  handlers.onEvent?.(parsed.name, payload);
  return "event";
}

export function useEventStream<T = unknown>(
  url: string,
  handlers: EventStreamHandlers<T>,
  deps: ReadonlyArray<unknown> = [],
  options: EventStreamOptions = {},
): { status: EventStreamStatus } {
  const [status, setStatus] = useState<EventStreamStatus>("connecting");
  // Stash the latest handlers + listen filter in refs so the effect
  // doesn't have to re-subscribe when the caller's inline handlers
  // change identity on every render. The ref-update effects run
  // after the render so the stream callbacks always see the latest
  // closures.
  const handlersRef = useRef(handlers);
  const listenRef = useRef<Set<string> | null>(
    options.listen ? new Set(options.listen) : null,
  );
  useEffect(() => {
    handlersRef.current = handlers;
  });
  useEffect(() => {
    listenRef.current = options.listen ? new Set(options.listen) : null;
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    let cancelled = false;
    let backoffIndex = 0;
    let backoffTimer: ReturnType<typeof setTimeout> | null = null;
    let activeController: AbortController | null = null;
    let reconnectScheduled = false;

    async function connect(): Promise<void> {
      if (cancelled) return;
      setStatus("connecting");
      const token = getStoredAccessToken();
      const controller = new AbortController();
      activeController = controller;
      let response: Response;
      try {
        response = await fetch(url, {
          method: "GET",
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            Accept: "text/event-stream",
            "Cache-Control": "no-cache",
          },
          credentials: "same-origin",
          cache: "no-store",
          signal: controller.signal,
        });
      } catch (err) {
        if (cancelled || controller.signal.aborted) return;
        const wrapped = err instanceof Error ? err : new Error(String(err));
        handlersRef.current.onError?.(wrapped);
        scheduleReconnect();
        return;
      }
      if (cancelled) {
        controller.abort();
        return;
      }
      if (!response.ok) {
        // 401 means the access token is gone — the topbar's hook will
        // never re-subscribe until the user changes, which only
        // happens on a real login/logout. Surface as an error and
        // stop reconnecting; the next mount of the hook (after a
        // reload or route change with a fresh token) will retry.
        // 404 is "the resource is gone" — e.g. a session that was
        // deleted between renders. Treat the same: surface and stop.
        if (response.status === 401 || response.status === 404) {
          setStatus("error");
          handlersRef.current.onError?.(
            new Error(`Stream connect failed: ${response.status}`),
          );
          return;
        }
        // 5xx / 403 / network blip: treat as recoverable.
        try {
          response.body?.cancel();
        } catch {
          /* best effort */
        }
        scheduleReconnect();
        return;
      }
      setStatus("open");
      backoffIndex = 0; // successful connect — reset the backoff
      const outcome = await readStream(
        response,
        {
          onSnapshot: (data) =>
            handlersRef.current.onSnapshot?.(data as T),
          onEvent: (name, data) =>
            handlersRef.current.onEvent?.(name, data as T),
          onError: (err) => handlersRef.current.onError?.(err),
          listen: listenRef.current,
        },
        controller.signal,
      );
      if (cancelled) return;
      // A clean close (the 5-min cap) still warrants a reconnect; an
      // error does too, but we already called onError inside
      // readStream so we don't surface twice.
      if (outcome === "closed" || outcome === "error") {
        setStatus("error");
        scheduleReconnect();
      }
    }

    function scheduleReconnect(): void {
      if (cancelled || reconnectScheduled) return;
      reconnectScheduled = true;
      const delay = BACKOFF_STEPS_MS[Math.min(backoffIndex, BACKOFF_STEPS_MS.length - 1)];
      backoffIndex = Math.min(backoffIndex + 1, BACKOFF_STEPS_MS.length - 1);
      backoffTimer = setTimeout(() => {
        reconnectScheduled = false;
        void connect();
      }, delay);
    }

    void connect();

    return () => {
      cancelled = true;
      if (backoffTimer) clearTimeout(backoffTimer);
      if (activeController) {
        try {
          activeController.abort();
        } catch {
          /* best effort */
        }
      }
      setStatus("closed");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, ...deps]);

  return { status };
}
