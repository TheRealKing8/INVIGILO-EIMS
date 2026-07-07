"""Liveness and readiness endpoints.

Liveness:  ``/api/health/``  — returns 200 if the process is alive.
Readiness: ``/api/ready/``   — returns 200 only when DB and Redis are
                              reachable and migrations are applied.

Both endpoints are unauthenticated, rate-limited only by Nginx, and
respond in < 50 ms on a healthy system.
"""
from __future__ import annotations

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from django.core.cache import cache


def _db_ok() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception:  # pragma: no cover — exercised only when DB is down
        return False


def _migrations_ok() -> bool:
    try:
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        for app, name in targets:
            if not executor.migration_plan((app, name)):
                # pending migration exists for this leaf
                return False
        return True
    except Exception:  # pragma: no cover
        return False


def _redis_ok() -> bool:
    try:
        cache.set("__invigilo_health__", "1", timeout=2)
        return cache.get("__invigilo_health__") == "1"
    except Exception:  # pragma: no cover
        return False


@api_view(["GET"])
@permission_classes([AllowAny])
def liveness(_request):  # type: ignore[no-untyped-def]
    """Liveness probe — always 200 as long as the process can respond."""
    return Response({"status": "alive"}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
def readiness(_request):  # type: ignore[no-untyped-def]
    """Readiness probe — 200 only when DB + Redis + migrations are healthy."""
    db_ok = _db_ok()
    redis_ok = _redis_ok()
    migrations_ok = _migrations_ok()
    healthy = db_ok and redis_ok and migrations_ok
    body = {
        "status": "ready" if healthy else "not_ready",
        "checks": {
            "database": "ok" if db_ok else "fail",
            "redis": "ok" if redis_ok else "fail",
            "migrations": "ok" if migrations_ok else "fail",
        },
    }
    return Response(body, status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE)
