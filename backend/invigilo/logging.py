"""Structured JSON logging.

Used in production so log shippers (Cloudwatch, Datadog, Loki) can ingest
events without a regex. The format is intentionally close to the
canonical ``{"timestamp", "level", "logger", "message"}`` shape with
optional ``request_id`` and ``actor_id`` fields populated by the
middlewares in this package.
"""
from __future__ import annotations

import json
import logging
from typing import Any


class JSONFormatter(logging.Formatter):
    """Render a log record as a single-line JSON document."""

    DEFAULT_KEYS = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Promote well-known extras to top-level keys.
        for key in ("request_id", "actor_id", "path", "method", "status"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Include any other custom extras.
        for key, value in record.__dict__.items():
            if key in self.DEFAULT_KEYS or key in payload or key.startswith("_"):
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except TypeError:
                payload[key] = repr(value)

        return json.dumps(payload, default=str)
