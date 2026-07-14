"""Auth views.

Two viewsets live here:

* :class:`AuthViewSet` — ``/api/v1/auth/`` (login, refresh, logout,
  password change, password reset, email verification, profile).

* :class:`UserViewSet` — ``/api/v1/users/`` (admin user management,
  gated by ``HasPermission('accounts.user.crud')``).
"""
from __future__ import annotations

import sys
from typing import Any

from django.contrib.auth import get_user_model
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.core.permissions import HasPermission

from . import services
from .models import User
from .serializers import (
    AdminPasswordResetSerializer,
    EmailVerificationConfirmSerializer,
    EmailVerificationRequestSerializer,
    LoginOTPVerifySerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RefreshRequestSerializer,
    SetRolesSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)

User = get_user_model()


class AuthViewSet(viewsets.ViewSet):
    """Stateless authentication endpoints.

    Most actions are ``POST`` and accept/return JSON. The ``profile``
    action is a ``GET`` / ``PATCH`` pair on the authenticated user.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(
                description=(
                    "Either a token pair (refresh set as httpOnly cookie) OR "
                    "{requires_otp: true, otp_token: '...'} when the user is "
                    "an admin and must complete the second step."
                )
            )
        },
    )
    def login(self, request: Any) -> Response:
        """Exchange email + password for an access + refresh pair.

        For users that must complete the OTP second step (currently
        any user whose ``primary_role_code`` is one of the 6 internal
        staff roles — SA, EO, HoD, Dean, Invigilator, Security
        Officer), this returns ``{requires_otp: true, otp_token: '...'}``
        with no JWT pair. The client posts ``{otp_token, code}`` to
        ``/auth/verify-otp/`` to complete the login. STUDENT and
        GUEST skip the OTP step.

        The refresh token is delivered as an ``invigilo_rt`` httpOnly
        cookie on the response. The access token is in the JSON body
        for the client to put in ``Authorization: Bearer …``.
        """
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.auth.authenticate(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if services.auth.requires_login_otp(user):
            otp_token, code = services.auth.issue_login_otp(user)
            # Fire-and-forget email send. We don't block the response
            # on the SMTP round-trip; the user's already been told
            # to expect a code.
            from .tasks import send_login_otp_email

            send_login_otp_email.delay(str(user.id), code)
            # Dev convenience: with the console email backend the OTP
            # body is printed by the email task, but the output can be
            # drowned out by request logs. Echo the code to the
            # runserver stdout with a clear banner so the developer
            # can copy it without hunting through the email block.
            # This is gated by ``DEBUG`` — prod never prints the
            # plain code anywhere.
            from django.conf import settings

            if settings.DEBUG:
                # Windows consoles default to cp1252 and crash on
                # the box-drawing characters. Reconfigure stdout to
                # UTF-8 so the banner prints cleanly on every
                # platform (a no-op on macOS/Linux where stdout is
                # already UTF-8).
                try:
                    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
                except (AttributeError, ValueError):
                    pass  # non-reconfigurable stdout (e.g. captured)
                print(
                    "\n"
                    "  ┌──────────────────────────────────────────────────────────┐\n"
                    f"  │  OTP for {user.email:<46s} │\n"
                    f"  │  code = {code:<46s} │\n"
                    f"  │  otp_token = {otp_token:<40s} │\n"
                    "  └──────────────────────────────────────────────────────────┘\n",
                    flush=True,
                )
            return Response(
                {"requires_otp": True, "otp_token": otp_token},
                status=status.HTTP_200_OK,
            )
        response = Response(status=status.HTTP_200_OK)
        response.data = services.auth.issue_token_pair(user, request=request, response=response)
        return response

    @extend_schema(
        request=LoginOTPVerifySerializer,
        responses={200: OpenApiResponse(description="Token pair (refresh set as httpOnly cookie)")},
    )
    def verify_otp(self, request: Any) -> Response:
        """Complete the second step of an admin login.

        Accepts ``{otp_token, code}`` from the first step. On success,
        issues the same access + refresh pair a normal login would.
        On any failure (wrong code, expired token, exhausted attempts,
        unknown token) returns a 400 with an opaque ``detail`` so the
        client can't distinguish failure modes.
        """
        serializer = LoginOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.auth.consume_login_otp(
            serializer.validated_data["otp_token"],
            serializer.validated_data["code"],
        )
        if user is None:
            return Response(
                {"detail": "Invalid or expired code."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        response = Response(status=status.HTTP_200_OK)
        response.data = services.auth.issue_token_pair(user, request=request, response=response)
        return response

    @extend_schema(
        request=UserCreateSerializer,
        responses={201: OpenApiResponse(description="User created + token pair (refresh as cookie)")},
    )
    def register(self, request: Any) -> Response:
        """Create a user account and immediately issue a token pair.

        The refresh token is set as an httpOnly cookie on the response.
        """
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        password = serializer.validated_data.pop("password", None) or None
        roles = serializer.validated_data.pop("roles", [])
        user = services.users.create_user(
            password=password,
            roles=roles,
            is_email_verified=True,
            **serializer.validated_data,
        )
        response = Response(status=status.HTTP_201_CREATED)
        response.data = services.auth.issue_token_pair(user, request=request, response=response)
        return response

    @extend_schema(
        request=RefreshRequestSerializer,
        responses={200: OpenApiResponse(description="New token pair (refresh rotated as cookie)")},
    )
    def refresh(self, request: Any) -> Response:
        """Rotate a refresh token, returning a new pair.

        Reads the refresh from the ``invigilo_rt`` cookie if present,
        otherwise from the request body. Sets a new cookie on the
        response so the browser's refresh is silently rotated. The
        body is accepted for non-browser clients (CLI, mobile) and
        for tests.
        """
        from .services.auth import read_refresh_from_request

        raw = read_refresh_from_request(request)
        if not raw and isinstance(request.data, dict):
            # Tolerate an empty body when the cookie already carried
            # the refresh; otherwise accept the body for non-browser
            # clients. A 400 if neither is present.
            raw = request.data.get("refresh") or None
        if not raw:
            return Response(
                {"detail": "Refresh token missing. Provide the invigilo_rt cookie or a 'refresh' body field."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        response = Response(status=status.HTTP_200_OK)
        response.data = services.auth.rotate_refresh(raw, request=request, response=response)
        return response

    @extend_schema(request=LogoutSerializer, responses={204: None})
    def logout(self, request: Any) -> Response:
        """Revoke the supplied refresh token and clear the cookie.

        The refresh can come from the cookie or the body. Either way
        the cookie is cleared on the way out so the browser drops it.
        An empty body is fine when the cookie carried the refresh.
        """
        from .services.auth import read_refresh_from_request, revoke_refresh, clear_refresh_cookie

        cookie_refresh = read_refresh_from_request(request)
        body_refresh: str = ""
        if isinstance(request.data, dict):
            raw_body = request.data.get("refresh")
            if isinstance(raw_body, str):
                body_refresh = raw_body
        raw = body_refresh or cookie_refresh or ""
        if raw:
            revoke_refresh(raw)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        # Always clear the cookie on logout, even if the body carried
        # the token. The browser doesn't need to keep it.
        if cookie_refresh:
            clear_refresh_cookie(response)
        return response

    @extend_schema(
        request=EmailVerificationRequestSerializer,
        responses={202: OpenApiResponse(description="Verification email queued")},
    )
    def request_verification(self, request: Any) -> Response:
        """Send (or re-send) a verification email."""
        serializer = EmailVerificationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = (serializer.validated_data.get("email") or "").strip().lower()
        user = User.all_objects.filter(email__iexact=email).first() if email else None
        if user is not None and not user.is_email_verified:
            token = services.auth.issue_email_verification(user)
            # The actual email send is handled by the Celery task below.
            from .tasks import send_verification_email

            send_verification_email.delay(str(user.id), token)
        # Return 202 unconditionally to avoid user-enumeration.
        return Response(status=status.HTTP_202_ACCEPTED)

    @extend_schema(
        request=EmailVerificationConfirmSerializer,
        responses={200: OpenApiResponse(description="User is now verified")},
    )
    def confirm_verification(self, request: Any) -> Response:
        """Consume a verification token."""
        serializer = EmailVerificationConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.auth.confirm_email_verification(serializer.validated_data["token"])
        return Response({"id": str(user.id), "is_email_verified": True}, status=status.HTTP_200_OK)

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={202: OpenApiResponse(description="If the email exists, a reset link is sent.")},
    )
    def request_password_reset(self, request: Any) -> Response:
        """Send a password-reset email if the user exists."""
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = services.auth.issue_password_reset(serializer.validated_data["email"])
        if token is not None:
            user = User.all_objects.get(email__iexact=serializer.validated_data["email"].strip().lower())
            from .tasks import send_password_reset_email

            send_password_reset_email.delay(str(user.id), token)
        return Response(status=status.HTTP_202_ACCEPTED)

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={204: None},
    )
    def confirm_password_reset(self, request: Any) -> Response:
        """Consume a reset token; set the new password."""
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.auth.confirm_password_reset(
            serializer.validated_data["token"],
            serializer.validated_data["new_password"],
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=PasswordChangeSerializer,
        responses={204: None},
    )
    def change_password(self, request: Any) -> Response:
        """Authenticated password change."""
        if not (request.user and request.user.is_authenticated):
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.users.change_password(
            request.user,
            current=serializer.validated_data["current"],
            new=serializer.validated_data["new"],
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses={200: UserSerializer})
    def me(self, request: Any) -> Response:
        """Return the authenticated user's profile.

        The :class:`UserSerializer` payload includes the user's live
        ``primary_role`` and the full ``roles`` set. The
        ``permissions`` claim on the access JWT is baked at login
        time and can drift after a role change — the frontend's
        ``/dashboard`` home re-fetches ``/auth/me/`` on mount to
        decide which role-specific branch to render, and trusts the
        live payload rather than the (potentially stale) JWT claim.
        """
        if not (request.user and request.user.is_authenticated):
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        data = UserSerializer(request.user).data
        # Live permission list — separate from the JWT's
        # ``permissions`` claim. The frontend uses this to refresh
        # client-side gates after a role change.
        data["permissions"] = sorted(
            request.user.permissions().values_list("codename", flat=True)
        )
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(request=UserUpdateSerializer, responses={200: UserSerializer})
    def update_me(self, request: Any) -> Response:
        """Update the authenticated user's profile."""
        if not (request.user and request.user.is_authenticated):
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        serializer = UserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.users.update_user(request.user, **serializer.validated_data)
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)

    # `me` and `update_me` must use JWT auth even though every other
    # action in this viewset is anonymous. Because we wire the viewset
    # manually with ``as_view({"get": "me", ...})`` instead of through
    # a router, DRF does not set ``self.action``; we infer the action
    # from the URL path.
    _AUTH_REQUIRED_PATH_SUFFIXES = ("/me/", "/me/update/")

    def _current_action(self) -> str:
        request = getattr(self, "request", None)
        if request is None:
            return ""
        path = (request.path or "").rstrip("/")
        for suffix in self._AUTH_REQUIRED_PATH_SUFFIXES:
            if path.endswith(suffix.rstrip("/")):
                # Map the URL back to the method name so future logic
                # can keep using ``self.action``-style names if it grows.
                return {"me/": "me", "me/update/": "update_me"}[suffix.lstrip("/")]
        return ""

    def get_authenticators(self):  # type: ignore[no-untyped-def]
        if self._current_action() in {"me", "update_me"}:
            return [JWTAuthentication()]
        return []

    def get_permissions(self):  # type: ignore[no-untyped-def]
        if self._current_action() in {"me", "update_me"}:
            return [IsAuthenticated()]
        return []


class UserViewSet(viewsets.ViewSet):
    """Admin endpoints for user management.

    All actions are gated by ``HasPermission('accounts.user.create')``
    by default. The two elevated actions — ``reset_password`` and
    ``set_roles`` — use a stricter codename resolved per-action via
    :meth:`get_permissions`. See ``03-use-cases.md`` §3.
    """

    permission_classes = [IsAuthenticated, HasPermission.with_codes("accounts.user.create")]

    # ---- action-specific permission overrides --------------------------
    # These actions require a stricter (narrower) codename than the
    # class-level ``accounts.user.create`` — password reset needs
    # ``accounts.user.reset_password`` (SA only), role assignment needs
    # ``accounts.role.assign`` (SA only). The mapping is per-action so
    # the broader CRUD actions keep working unchanged.
    _ACTION_PERMISSION_OVERRIDES = {
        "reset_password": ("accounts.user.reset_password",),
        "set_roles": ("accounts.role.assign",),
    }

    def get_permissions(self):  # type: ignore[no-untyped-def]
        codes = self._ACTION_PERMISSION_OVERRIDES.get(self.action)
        if codes is not None:
            # DRF expects permission *instances* from get_permissions.
            # The class-level ``permission_classes`` is auto-instantiated
            # by DRF; here we have to instantiate explicitly.
            return [IsAuthenticated(), HasPermission.with_codes(*codes)()]
        return super().get_permissions()

    def list(self, request: Any) -> Response:
        users = User.objects.all().order_by("email")
        return Response(UserSerializer(users, many=True).data, status=status.HTTP_200_OK)

    def retrieve(self, request: Any, pk: str | None = None) -> Response:
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)

    def create(self, request: Any) -> Response:
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        password = serializer.validated_data.pop("password", None) or None
        roles = serializer.validated_data.pop("roles", [])
        user = services.users.create_user(
            assigned_by=request.user if request.user.is_authenticated else None,
            password=password,
            roles=roles,
            **serializer.validated_data,
        )
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request: Any, pk: str | None = None) -> Response:
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = UserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.users.update_user(user, **serializer.validated_data)
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)

    @extend_schema(responses={204: None})
    def destroy(self, request: Any, pk: str | None = None) -> Response:
        """Soft-delete (disable) a user."""
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        user.soft_delete()
        # Revoke all refresh tokens.
        from .models import RefreshToken

        RefreshToken.objects.filter(user=user, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses={204: None})
    def unlock(self, request: Any, pk: str | None = None) -> Response:
        """Clear a user's failed-login counter and lockout."""
        try:
            user = User.all_objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        services.users.unlock_user(user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=AdminPasswordResetSerializer, responses={204: None})
    def reset_password(self, request: Any, pk: str | None = None) -> Response:
        """Set a new password for the given user.

        The service runs the full ``validate_password`` complexity check
        (12+ chars, 3-of-4 complexity, common-password block) on top of
        the serializer's cheap ``min_length=12`` gate. Refresh tokens
        are revoked so the affected user must sign in again.

        Gated by ``accounts.user.reset_password`` — SYSTEM_ADMINISTRATOR
        only. See :meth:`get_permissions`.
        """
        try:
            user = User.all_objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = AdminPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.users.admin_reset_password(
            user, new=serializer.validated_data["new_password"]
        )
        from .models import RefreshToken

        RefreshToken.objects.filter(user=user, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=SetRolesSerializer, responses={200: UserSerializer})
    def set_roles(self, request: Any, pk: str | None = None) -> Response:
        """Replace the user's full role set with the given list.

        Unknown role codes raise a 422 (the serializer catches them
        before the service is called). Empty list is allowed — the
        caller is responsible for not stranding their own admin
        account; the detail-page UI hides the "Save roles" button
        when the resulting role set would lock the current admin out.

        Gated by ``accounts.role.assign`` — SYSTEM_ADMINISTRATOR only.
        See :meth:`get_permissions`.
        """
        try:
            user = User.all_objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = SetRolesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.users.set_user_roles(
            user,
            serializer.validated_data["roles"],
            assigned_by=request.user if request.user.is_authenticated else None,
        )
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


__all__ = ["AuthViewSet", "UserViewSet"]
