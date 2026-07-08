"""Auth views.

Two viewsets live here:

* :class:`AuthViewSet` — ``/api/v1/auth/`` (login, refresh, logout,
  password change, password reset, email verification, profile).

* :class:`UserViewSet` — ``/api/v1/users/`` (admin user management,
  gated by ``HasPermission('accounts.user.crud')``).
"""
from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import HasPermission

from . import services
from .models import User
from .serializers import (
    EmailVerificationConfirmSerializer,
    EmailVerificationRequestSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RefreshRequestSerializer,
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
        responses={200: OpenApiResponse(description="Token pair + user")},
    )
    def login(self, request: Any) -> Response:
        """Exchange email + password for an access + refresh pair."""
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.auth.authenticate(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        return Response(
            services.auth.issue_token_pair(user, request=request),
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=UserCreateSerializer,
        responses={201: OpenApiResponse(description="User created + token pair")},
    )
    def register(self, request: Any) -> Response:
        """Create a user account and immediately issue a token pair."""
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
        return Response(
            services.auth.issue_token_pair(user, request=request),
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=RefreshRequestSerializer,
        responses={200: OpenApiResponse(description="New token pair")},
    )
    def refresh(self, request: Any) -> Response:
        """Rotate a refresh token, returning a new pair."""
        serializer = RefreshRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            services.auth.rotate_refresh(serializer.validated_data["refresh"]),
            status=status.HTTP_200_OK,
        )

    @extend_schema(request=LogoutSerializer, responses={204: None})
    def logout(self, request: Any) -> Response:
        """Revoke the supplied refresh token."""
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.auth.revoke_refresh(serializer.validated_data.get("refresh", ""))
        return Response(status=status.HTTP_204_NO_CONTENT)

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
        """Return the authenticated user's profile."""
        if not (request.user and request.user.is_authenticated):
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)

    @extend_schema(request=UserUpdateSerializer, responses={200: UserSerializer})
    def update_me(self, request: Any) -> Response:
        """Update the authenticated user's profile."""
        if not (request.user and request.user.is_authenticated):
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        serializer = UserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.users.update_user(request.user, **serializer.validated_data)
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)


class UserViewSet(viewsets.ViewSet):
    """Admin endpoints for user management.

    All actions are gated by ``HasPermission('accounts.user.crud')`` —
    see ``03-use-cases.md`` §3.
    """

    permission_classes = [IsAuthenticated, HasPermission.with_codes("accounts.user.create")]

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


__all__ = ["AuthViewSet", "UserViewSet"]
