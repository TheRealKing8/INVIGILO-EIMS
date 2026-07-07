"""DRF serializers for the accounts app.

Serializers are intentionally narrow — they validate input and shape
output, they do not run business logic. Business logic lives in
``services/``.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from .models import Role

User = get_user_model()


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ("id", "code", "name", "description", "is_active", "created_at")
        read_only_fields = ("id", "created_at")


class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    primary_role = serializers.CharField(source="primary_role_code", read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "phone",
            "avatar_url",
            "time_zone",
            "is_active",
            "is_email_verified",
            "is_staff",
            "is_superuser",
            "last_login_at",
            "failed_login_count",
            "locked_until",
            "created_at",
            "updated_at",
            "primary_role",
            "roles",
        )
        read_only_fields = (
            "id",
            "is_active",
            "is_staff",
            "is_superuser",
            "last_login_at",
            "failed_login_count",
            "locked_until",
            "created_at",
            "updated_at",
            "primary_role",
            "roles",
        )

    def get_roles(self, obj: User) -> list[dict[str, str]]:
        return [{"id": str(r.id), "code": r.code, "name": r.name} for r in obj.roles()]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    roles = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
    )

    class Meta:
        model = User
        fields = (
            "email",
            "full_name",
            "phone",
            "time_zone",
            "is_email_verified",
            "password",
            "roles",
        )

    def validate_email(self, value: str) -> str:
        return (value or "").strip().lower()

    def validate_roles(self, value: list[str]) -> list[str]:
        known = set(Role.objects.filter(is_active=True).values_list("code", flat=True))
        unknown = [r for r in value if r not in known]
        if unknown:
            raise serializers.ValidationError(f"Unknown role code(s): {unknown}")
        return value


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "full_name",
            "phone",
            "avatar_url",
            "time_zone",
        )


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class RefreshRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True)


class PasswordChangeSerializer(serializers.Serializer):
    current = serializers.CharField(write_only=True)
    new = serializers.CharField(write_only=True)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)


class EmailVerificationRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)


class EmailVerificationConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(write_only=True)


class InvigiloTokenObtainPairSerializer(serializers.Serializer):
    """A drop-in replacement for SimpleJWT's default obtain-pair serializer.

    The view in ``AuthViewSet`` calls :func:`apps.accounts.services.auth.authenticate`
    first, then :func:`issue_token_pair`, so this serializer is mostly a
    placeholder for OpenAPI generation.
    """

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class InvigiloTokenRefreshSerializer(TokenRefreshSerializer):
    """Custom refresh serializer.

    We use it in OpenAPI generation; the actual refresh logic lives in
    :func:`apps.accounts.services.auth.rotate_refresh`.
    """

    pass


__all__ = [
    "EmailVerificationConfirmSerializer",
    "EmailVerificationRequestSerializer",
    "InvigiloTokenObtainPairSerializer",
    "InvigiloTokenRefreshSerializer",
    "LoginSerializer",
    "LogoutSerializer",
    "PasswordChangeSerializer",
    "PasswordResetConfirmSerializer",
    "PasswordResetRequestSerializer",
    "RefreshRequestSerializer",
    "RoleSerializer",
    "UserCreateSerializer",
    "UserSerializer",
    "UserUpdateSerializer",
]
