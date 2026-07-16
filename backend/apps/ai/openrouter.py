"""OpenRouter API client.

A thin async wrapper around the OpenAI-shaped Chat Completions
endpoint that OpenRouter exposes. Three things matter:

* The API key is read from ``settings.OPENROUTER_API_KEY`` at call
  time (never logged, never sent to the frontend). The client
  raises :class:`OpenRouterError` for any non-200 response so the
  caller can decide whether to retry, fall back, or surface a 503.
* A short timeout (``settings.OPENROUTER_TIMEOUT_SECONDS``,
  default 20s) bounds the user-facing latency. Retries are
  bounded by ``settings.OPENROUTER_MAX_RETRIES`` (default 1) and
  only fire on 5xx and connection errors — 4xx means the user
  asked for something the model rejected, retrying won't help.
* Returns a :class:`LLMResult` with the parsed content + token
  counts + latency, so the view can log every call to the
  ``invigilo.ai`` logger.

The module is intentionally tiny. Adding features (function
calling, JSON mode, vision, etc.) is a follow-up — the current
spec just needs free-form natural-language replies grounded in
the live DB context the caller passes in.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Iterator

import httpx
from django.conf import settings


logger = logging.getLogger("invigilo.ai.openrouter")


class OpenRouterError(RuntimeError):
    """Raised on any non-success response from the OpenRouter API.

    The ``status_code`` is the HTTP status (or 0 for network
    errors). The ``detail`` is the parsed error body or the raw
    text if the body wasn't JSON.
    """

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"OpenRouter {status_code}: {detail[:200]}")
        self.status_code = status_code
        self.detail = detail


@dataclass
class LLMResult:
    """The parsed response from a single chat call."""

    content: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    model: str


@dataclass
class LLMToken:
    """One delta from a streaming chat call.

    ``kind`` is either ``"token"`` (a content delta — see ``delta``)
    or ``"error"`` (an upstream failure — see ``detail``). The
    streaming consumer in :mod:`apps.realtime.views` ignores other
    event names — OpenRouter only sends ``data: { ... }`` chunks
    ending in ``[DONE]``.
    """

    kind: str  # "token" | "error"
    delta: str = ""
    detail: str = ""


def _retryable(status_code: int) -> bool:
    """Only 5xx and 429 are worth retrying; 4xx means the request
    is malformed or refused and a second call will fail the same way."""
    return status_code == 429 or 500 <= status_code < 600


async def chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 600,
) -> LLMResult:
    """Call the OpenRouter Chat Completions API.

    ``messages`` is the standard OpenAI shape:
    ``[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]``.

    The function does NOT do rate-limit backoff — DRF's throttle
    is the rate-limit layer. The single retry here is for transient
    5xx / 429 from the upstream.
    """
    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        # Caller should check before invoking; this is a defensive
        # guard so an empty key never hits the wire.
        raise OpenRouterError(0, "OPENROUTER_API_KEY is not set")

    base_url = settings.OPENROUTER_BASE_URL.rstrip("/")
    chosen_model = model or settings.OPENROUTER_MODEL
    timeout = settings.OPENROUTER_TIMEOUT_SECONDS
    max_retries = max(0, settings.OPENROUTER_MAX_RETRIES)

    payload: dict[str, Any] = {
        "model": chosen_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        # OpenRouter's attribution headers — recommended by their docs.
        "HTTP-Referer": "https://invigilo.local",
        "X-Title": "Invigilo",
    }

    started = time.monotonic()
    last_err: OpenRouterError | None = None
    attempts = max_retries + 1
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(attempts):
            try:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
            except httpx.HTTPError as exc:
                last_err = OpenRouterError(0, f"network error: {exc!s}")
                # Network errors are always retryable.
                if attempt + 1 < attempts:
                    continue
                raise last_err from exc

            if response.status_code < 400:
                data = response.json()
                try:
                    content = data["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError) as exc:
                    raise OpenRouterError(
                        response.status_code,
                        f"unexpected response shape: {exc!s}",
                    ) from exc
                usage = data.get("usage") or {}
                latency_ms = int((time.monotonic() - started) * 1000)
                return LLMResult(
                    content=content,
                    prompt_tokens=int(usage.get("prompt_tokens") or 0),
                    completion_tokens=int(usage.get("completion_tokens") or 0),
                    latency_ms=latency_ms,
                    model=chosen_model,
                )

            # Non-2xx: try to extract a useful error body.
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            last_err = OpenRouterError(response.status_code, str(detail))
            if _retryable(response.status_code) and attempt + 1 < attempts:
                continue
            raise last_err

    # Loop should always return or raise; defensive raise.
    assert last_err is not None
    raise last_err


__all__ = ["OpenRouterError", "LLMResult", "LLMToken", "chat", "stream_chat"]


# ---------------------------------------------------------------------------
# Streaming variant
# ---------------------------------------------------------------------------
async def stream_chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 600,
) -> Iterator[LLMToken]:
    """Stream the OpenRouter reply token-by-token.

    Yields :class:`LLMToken` events. ``kind="token"`` carries a
    string ``delta`` (a single content fragment, often a few
    characters). ``kind="error"`` carries a ``detail`` string
    and is the last event the generator yields — callers should
    stop iterating and surface the error.

    The OpenRouter wire format is OpenAI-compatible SSE:

        data: {"choices": [{"delta": {"content": "Hel"}, ...}]}
        data: {"choices": [{"delta": {"content": "lo"}, ...}]}
        data: [DONE]

    We parse each ``data:`` line as JSON and pull out
    ``choices[0].delta.content``. A ``[DONE]`` sentinel ends the
    stream cleanly. Any non-JSON line is skipped (OpenRouter
    sometimes sends a comment line; harmless).

    We do NOT retry the streaming path — the first chunk is
    already on the wire by the time a retry would matter, and
    the client just falls back to the non-streaming endpoint.
    """
    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        # Caller should check before invoking; defensive guard.
        yield LLMToken(kind="error", detail="OPENROUTER_API_KEY is not set")
        return

    base_url = settings.OPENROUTER_BASE_URL.rstrip("/")
    chosen_model = model or settings.OPENROUTER_MODEL
    timeout = settings.OPENROUTER_TIMEOUT_SECONDS

    payload: dict[str, Any] = {
        "model": chosen_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://invigilo.local",
        "X-Title": "Invigilo",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                if response.status_code >= 400:
                    # Drain the body so the connection is released,
                    # then surface a single error event.
                    body = await response.aread()
                    try:
                        detail = body.decode("utf-8", errors="replace")[:200]
                    except Exception:  # noqa: BLE001
                        detail = f"status {response.status_code}"
                    yield LLMToken(kind="error", detail=detail)
                    return
                # Walk the byte stream, line by line.
                async for raw_line in response.aiter_lines():
                    line = raw_line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    payload_str = line[5:].strip()
                    if payload_str == "[DONE]":
                        return
                    try:
                        chunk = json.loads(payload_str)
                    except ValueError:
                        # Malformed chunk — skip and keep going.
                        continue
                    try:
                        delta = chunk["choices"][0]["delta"].get("content")
                    except (KeyError, IndexError, TypeError, AttributeError):
                        # Some chunks are usage-only or finish_reason
                        # markers; just skip them.
                        continue
                    if delta:
                        yield LLMToken(kind="token", delta=delta)
    except httpx.HTTPError as exc:
        # Connection dropped, timeout, TLS error — surface as a
        # single error event so the consumer can fall back to the
        # non-streaming endpoint.
        yield LLMToken(kind="error", detail=f"network error: {exc!s}")
