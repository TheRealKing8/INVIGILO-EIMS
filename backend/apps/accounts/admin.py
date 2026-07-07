"""Django admin registrations for the accounts app."""
from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    EmailVerification,
    PasswordReset,
    Permission,
    RefreshToken,
    Role,
    RolePermission,
    User,
    UserRole,
)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Admin view of the custom user.

    The default Django UserAdmin is overridden to use email as the
    identifier and to surface the roles/permissions columns.
    """

    ordering = ("email",)
    list_display = ("email", "full_name", "is_active", "is_email_verified", "is_staff", "is_superuser")
    list_filter = ("is_active", "is_email_verified", "is_staff", "is_superuser")
    search_fields = ("email", "full_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("full_name", "phone", "avatar_url", "time_zone")}),
        (
            "Status",
            {
                "fields": (
                    "is_active",
                    "is_email_verified",
                    "is_staff",
                    "is_superuser",
                    "failed_login_count",
                    "locked_until",
                    "last_login_at",
                )
            },
        ),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("Timestamps", {"fields": ("created_at", "updated_at", "deactivated_at")}),
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "deactivated_at",
        "last_login_at",
        "failed_login_count",
        "locked_until",
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "password1", "password2"),
            },
        ),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    search_fields = ("code", "name")
    list_filter = ("is_active",)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("codename", "name")
    search_fields = ("codename", "name")


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "permission")
    list_filter = ("role",)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "assigned_by", "created_at")
    list_filter = ("role",)
    search_fields = ("user__email", "role__code")


@admin.register(RefreshToken)
class RefreshTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at", "revoked_at", "created_at")
    list_filter = ("revoked_at",)
    search_fields = ("user__email",)
    readonly_fields = ("token_hash", "user", "expires_at", "created_at", "updated_at")


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at", "used_at")
    readonly_fields = ("token_hash",)


@admin.register(PasswordReset)
class PasswordResetAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at", "used_at")
    readonly_fields = ("token_hash",)
