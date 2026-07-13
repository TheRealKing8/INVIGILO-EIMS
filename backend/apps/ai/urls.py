"""URL config for the AI assistant app."""
from __future__ import annotations

from django.urls import path

from .views import ChatView


urlpatterns = [
    path("chat/", ChatView.as_view(), name="ai-chat"),
]
