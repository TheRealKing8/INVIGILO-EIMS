"""AI assistant.

A pragmatic, DB-fed assistant. The endpoint gathers live context
(active exam period, today's sessions, latest allocation run, open
conflicts, open incidents) and composes a rule-based reply — no LLM
in the loop. The reply is grounded in the actual database state, so
the EO can ask "how many open incidents?" and get a number, not a
hallucination.
"""
