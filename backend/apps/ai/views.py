"""HTTP layer for the AI assistant.

A single POST endpoint. The frontend sends a free-form message and
gets back ``{reply, suggestions, intent, context}``. The reply is
the markdown string; ``suggestions`` are tap-to-fill chips the
frontend renders under the response.
"""
from __future__ import annotations

import logging

from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import build_context, compose_reply


logger = logging.getLogger("invigilo.ai")


def _context_to_dict(ctx) -> dict:
    """Serialise the live context the reply was built from. Kept
    small — the assistant answer is the product; the context is a
    debugging aid for the frontend "what did the AI see?" tooltip."""
    return {
        "active_period": ctx.period.code if ctx.period else None,
        "upcoming_session_count": len(ctx.upcoming_sessions),
        "open_conflict_count": len(ctx.open_conflicts),
        "open_incident_count": len(ctx.open_incidents),
        "invigilator_total": ctx.invigilator_total,
        "invigilator_unavailable_today": ctx.invigilator_unavailable_today,
        "latest_run_id": str(ctx.latest_run.id) if ctx.latest_run else None,
        "latest_run_coverage": (
            float(ctx.latest_run.capacity_utilisation) if ctx.latest_run else None
        ),
        "generated_at": ctx.generated_at.isoformat(),
    }


@extend_schema(
    tags=["ai"],
    summary="Ask the AI assistant a question.",
    description=(
        "The assistant is fed live data from the database (active period, "
        "upcoming sessions, open conflicts and incidents, latest engine run). "
        "It is rule-based, not an LLM, so it can only answer about facts it "
        "can read from the DB. Replies are deterministic for the same question "
        "at the same moment."
    ),
    request={"application/json": {"type": "object", "properties": {"message": {"type": "string"}}}},
    responses={200: {"type": "object"}},
    examples=[
        OpenApiExample(
            "Status question",
            value={"message": "What's the status of the current cycle?"},
            request_only=True,
        ),
    ],
)
class ChatView(APIView):
    permission_classes = [IsAuthenticated]

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
        ctx = build_context()
        reply, suggestions, intent = compose_reply(message, ctx)
        logger.info(
            "ai.chat user=%s intent=%s message=%r",
            getattr(request.user, "email", "anon"),
            intent,
            message[:80],
        )
        return Response(
            {
                "reply": reply,
                "suggestions": suggestions,
                "intent": intent,
                "context": _context_to_dict(ctx),
            },
            status=status.HTTP_200_OK,
        )
