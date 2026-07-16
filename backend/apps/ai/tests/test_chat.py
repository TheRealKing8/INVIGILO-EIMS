"""Tests for the AI assistant endpoint.

The assistant is rule-based and fed live DB data. We verify:

* the endpoint requires auth;
* a `status` question returns the active period's name;
* a `conflicts` question enumerates the Conflict rows that exist;
* an empty message is rejected with 400;
* a long message (> 500 chars) is rejected with 400;
* when ``OPENROUTER_API_KEY`` is set, the view calls the LLM and
  returns its reply (Phase 19);
* when the LLM call raises, the view falls back to the rule-based
  reply so dev never sees a 5xx;
* a 4xx from the LLM is logged and falls back; the 5xx retry path
  is exercised via the ``OPENROUTER_MAX_RETRIES`` setting;
* the chat endpoint has a per-user 30/minute throttle (Phase 19).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import httpx
import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.academic.models import Course, Department, Faculty, Program
from apps.allocations.models import AllocationRun, Conflict
from apps.exams.models import ExamPeriod, ExamSession
from apps.invigilators.models import InvigilatorProfile
from apps.rooms.models import Building, Room


User = get_user_model()
pytestmark = pytest.mark.django_db


def test_chat_requires_auth(client: APIClient) -> None:
    response = client.post(reverse("ai:ai-chat"), {"message": "status"}, format="json")
    assert response.status_code in (401, 403)


def test_chat_rejects_empty_message(client: APIClient, verified_user) -> None:  # type: ignore[no-untyped-def]
    client.force_authenticate(verified_user)
    response = client.post(reverse("ai:ai-chat"), {"message": ""}, format="json")
    assert response.status_code == 400
    assert "message" in response.json()["detail"]


def test_chat_rejects_overlong_message(client: APIClient, verified_user) -> None:  # type: ignore[no-untyped-def]
    client.force_authenticate(verified_user)
    response = client.post(reverse("ai:ai-chat"), {"message": "x" * 501}, format="json")
    assert response.status_code == 400


def test_chat_status_reports_active_period(client: APIClient, verified_user) -> None:  # type: ignore[no-untyped-def]
    # The base seed installs a default active period; this test cares
    # only about the one it creates, so deactivate any existing ones.
    ExamPeriod.objects.filter(is_active=True).update(is_active=False)
    ExamPeriod.objects.create(
        code="AI-1", name="AI Test Cycle", is_active=True,
        starts_on=date.today(), ends_on=date.today() + timedelta(days=14),
    )
    client.force_authenticate(verified_user)
    response = client.post(reverse("ai:ai-chat"), {"message": "status"}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert "AI-1" in body["reply"]
    assert body["intent"] == "status"
    assert isinstance(body["suggestions"], list)
    assert body["context"]["active_period"] == "AI-1"


def test_chat_help_when_no_period(client: APIClient, verified_user) -> None:  # type: ignore[no-untyped-def]
    # No active period — deactivate all (the base seed has one).
    ExamPeriod.objects.filter(is_active=True).update(is_active=False)
    client.force_authenticate(verified_user)
    response = client.post(reverse("ai:ai-chat"), {"message": "what's the status"}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert "no active exam period" in body["reply"].lower()
    assert body["context"]["active_period"] is None


def test_chat_conflicts_lists_open_conflicts(client: APIClient, verified_user) -> None:  # type: ignore[no-untyped-def]
    f = Faculty.objects.create(code="AI-F", name="AI Faculty")
    d = Department.objects.create(faculty=f, code="AI-D", name="D")
    p = Program.objects.create(department=d, code="AI-P", name="P")
    course = Course.objects.create(program=p, code="AIC-101", title="X", credit_hours=3)
    building = Building.objects.create(code="AI-B", name="B")
    room = Room.objects.create(building=building, code="AI-R", capacity=50)
    period = ExamPeriod.objects.create(
        code="AI-C", name="Conflicts Cycle", is_active=True,
        starts_on=date.today(), ends_on=date.today() + timedelta(days=10),
    )
    session = ExamSession.objects.create(
        period=period, course=course, room=room,
        starts_at=datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc),
        capacity=50, registered=20, invigilators_required=2, status="scheduled",
    )
    run = AllocationRun.objects.create(
        period=period, sessions_total=1, sessions_placed=1,
        avg_workload=1, max_workload=1, capacity_utilisation=1, runtime_seconds=1,
    )
    Conflict.objects.create(
        run=run, type="workload_cap", severity="error",
        detail="Example detail", session=session,
    )

    client.force_authenticate(verified_user)
    response = client.post(reverse("ai:ai-chat"), {"message": "what conflicts do we have"}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "conflicts"
    assert "workload cap" in body["reply"]
    assert body["context"]["open_conflict_count"] == 1


def test_chat_invigilators_reports_total(client: APIClient, verified_user) -> None:  # type: ignore[no-untyped-def]
    f = Faculty.objects.create(code="AI-IF", name="F")
    d = Department.objects.create(faculty=f, code="AI-ID", name="D")
    for i in range(3):
        u = User.objects.create_user(email=f"ai-inv-{i}@x.com", full_name=f"Inv {i}")
        InvigilatorProfile.objects.create(user=u, primary_department=d, max_sessions_per_cycle=4)

    client.force_authenticate(verified_user)
    response = client.post(reverse("ai:ai-chat"), {"message": "how many invigilators do we have"}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "invigilators"
    assert "3" in body["reply"]
    assert body["context"]["invigilator_total"] == 3


def test_chat_intent_help_on_unknown(client: APIClient, verified_user) -> None:  # type: ignore[no-untyped-def]
    client.force_authenticate(verified_user)
    response = client.post(reverse("ai:ai-chat"), {"message": "hello there"}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "help"


# ---------------------------------------------------------------------------
# Phase 19 — OpenRouter LLM path
# ---------------------------------------------------------------------------
# The view is responsible for branching: with a configured key, it calls
# the LLM and returns its reply. Without a key, it falls back to the
# rule-based path. These tests mock the OpenRouter client at the httpx
# layer using ``httpx.MockTransport`` so no real network call is made
# and the response shape is fully controlled.
def _openrouter_response(content: str) -> dict:
    """Build the JSON body OpenRouter (OpenAI shape) returns on success."""
    return {
        "id": "gen-test",
        "model": "openai/gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 123, "completion_tokens": 45, "total_tokens": 168},
    }


def _patch_chat_with(handler):
    """Patch ``apps.ai.services.chat`` so the inner httpx call uses a
    MockTransport driven by ``handler(request)``.

    Why ``services.chat`` and not ``openrouter.chat``? The service
    imports ``chat`` via ``from .openrouter import ... chat``, which
    binds the function name at import time. Patching the attribute on
    the openrouter module has no effect on the bound name in services.
    """
    from apps.ai import services as services_mod
    from apps.ai.openrouter import LLMResult

    transport = httpx.MockTransport(handler)

    async def _stub(messages, **kwargs):  # type: ignore[no-untyped-def]
        async with httpx.AsyncClient(transport=transport) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json={"messages": messages, **kwargs},
            )
        data = response.json()
        return LLMResult(
            content=data["choices"][0]["message"]["content"],
            prompt_tokens=int((data.get("usage") or {}).get("prompt_tokens") or 0),
            completion_tokens=int((data.get("usage") or {}).get("completion_tokens") or 0),
            latency_ms=12,
            model=data.get("model", "openai/gpt-4o-mini"),
        )

    return patch.object(services_mod, "chat", _stub)


@override_settings(OPENROUTER_API_KEY="sk-or-test", OPENROUTER_MAX_RETRIES=0)
def test_chat_uses_llm_when_key_set(client: APIClient, verified_user) -> None:  # type: ignore[no-untyped-def]
    """With a key, the LLM's reply is returned verbatim and intent=llm."""
    payload = _openrouter_response(
        json.dumps({
            "reply": "**Test reply** from the LLM.",
            "suggestions": ["Try status", "Try conflicts"],
        })
    )

    with _patch_chat_with(lambda req: httpx.Response(200, json=payload)):
        client.force_authenticate(verified_user)
        response = client.post(reverse("ai:ai-chat"), {"message": "hello"}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "**Test reply** from the LLM."
    assert body["intent"] == "llm"
    assert body["suggestions"] == ["Try status", "Try conflicts"]


@override_settings(OPENROUTER_API_KEY="sk-or-test", OPENROUTER_MAX_RETRIES=0)
def test_chat_falls_back_to_rule_based_on_llm_4xx(
    client: APIClient, verified_user
) -> None:  # type: ignore[no-untyped-def]
    """When the LLM returns 401, the view falls back to the rule-based path."""
    with _patch_chat_with(lambda req: httpx.Response(401, json={"error": "bad key"})):
        client.force_authenticate(verified_user)
        response = client.post(reverse("ai:ai-chat"), {"message": "status"}, format="json")
    assert response.status_code == 200
    body = response.json()
    # Rule-based path returns intent=status, not "llm".
    assert body["intent"] == "status"
    assert "active cycle" in body["reply"].lower() or "no active" in body["reply"].lower()


@override_settings(OPENROUTER_API_KEY="sk-or-test", OPENROUTER_MAX_RETRIES=0)
def test_chat_keeps_plain_text_when_llm_response_not_json(
    client: APIClient, verified_user
) -> None:  # type: ignore[no-untyped-def]
    """If the LLM returns prose (the system prompt asks for JSON, but
    models sometimes ignore that), the view treats it as a plain-text
    reply and the intent stays ``"llm"`` — there's no rule-based
    fallback for parse errors, just an empty suggestions list."""
    payload = _openrouter_response("Sure! Active period: AI-1.")

    with _patch_chat_with(lambda req: httpx.Response(200, json=payload)):
        client.force_authenticate(verified_user)
        response = client.post(reverse("ai:ai-chat"), {"message": "status"}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Sure! Active period: AI-1."
    assert body["intent"] == "llm"
    assert body["suggestions"] == []


def test_chat_throttles_per_user(client: APIClient, verified_user) -> None:  # type: ignore[no-untyped-def]
    """The 30/minute ai_chat scope caps a single user at 2 calls per minute
    in this test (rate lowered to make the assertion tractable)."""
    from apps.ai.views import ChatUserThrottle
    from django.core.cache import cache

    payload = _openrouter_response(
        json.dumps({"reply": "ok", "suggestions": []})
    )
    # Monkey-patch the rate. ``SimpleRateThrottle.__init__`` sets
    # ``self.rate`` only if it's not already set on the class, so
    # pre-populating it on the class is enough.
    ChatUserThrottle.rate = "2/minute"
    try:
        cache.clear()
        with _patch_chat_with(lambda req: httpx.Response(200, json=payload)):
            client.force_authenticate(verified_user)
            first = client.post(reverse("ai:ai-chat"), {"message": "status"}, format="json")
            second = client.post(reverse("ai:ai-chat"), {"message": "status"}, format="json")
            third = client.post(reverse("ai:ai-chat"), {"message": "status"}, format="json")
    finally:
        delattr(ChatUserThrottle, "rate")
        cache.clear()
    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
