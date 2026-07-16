"""URL configuration for ``/api/v1/auth/``."""
from __future__ import annotations

from django.urls import path

from .views import AuthViewSet


def _bind(method: str, name: str):  # type: ignore[no-untyped-def]
    """Bind a ViewSet method as a URL handler."""
    view = AuthViewSet.as_view({method: name})
    return view


urlpatterns = [
    path("login/", _bind("post", "login"), name="auth-login"),
    path("select-role/", _bind("post", "select_role"), name="auth-select-role"),
    path("verify-otp/", _bind("post", "verify_otp"), name="auth-verify-otp"),
    path("register/", _bind("post", "register"), name="auth-register"),
    path("refresh/", _bind("post", "refresh"), name="auth-refresh"),
    path("logout/", _bind("post", "logout"), name="auth-logout"),
    path("me/", _bind("get", "me"), name="auth-me"),
    path("me/update/", _bind("patch", "update_me"), name="auth-me-update"),
    path("password/change/", _bind("post", "change_password"), name="auth-password-change"),
    path("password/reset/", _bind("post", "request_password_reset"), name="auth-password-reset-request"),
    path("password/reset/confirm/", _bind("post", "confirm_password_reset"), name="auth-password-reset-confirm"),
    path("email/verify/request/", _bind("post", "request_verification"), name="auth-verify-request"),
    path("email/verify/confirm/", _bind("post", "confirm_verification"), name="auth-verify-confirm"),
]
