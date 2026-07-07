"""Celery application bootstrap.

The app is created here and exposed as ``invigilo.celery_app`` so the worker
can be started with::

    celery -A invigilo worker -l info
    celery -A invigilo beat  -l info

Task discovery is wired to look under each app's ``tasks`` module.
"""
from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "invigilo.settings.dev")

app = Celery("invigilo")

# Pull configuration from Django settings, prefixed with CELERY_.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Discover tasks in each installed app's tasks module.
app.autodiscover_tasks()


@app.on_after_configure.connect
def _setup_periodic_tasks(sender: Celery, **kwargs) -> None:  # type: ignore[no-untyped-def]
    """Register periodic tasks.

    Kept empty in Phase 2. The clean-up jobs (refresh-token GC, audit log
    retention) are added in later phases when their owners exist.
    """
    _ = crontab  # silence unused-import warnings until the first job lands
