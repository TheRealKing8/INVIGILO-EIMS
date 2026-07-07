"""INVIGILO Django project package.

Exposing ``celery_app`` here makes the project importable as a Celery
application::

    celery -A invigilo worker -l info
"""
from __future__ import annotations

from .celery import app as celery_app

__all__ = ["celery_app"]
