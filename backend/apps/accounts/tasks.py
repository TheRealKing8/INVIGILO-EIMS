"""Celery tasks for the accounts app.

Outbound email is delivered through Celery so the API request doesn't
block on SMTP. Failures are retried up to 3 times with exponential
backoff (NFR-NOT-04).
"""
from __future__ import annotations

import logging
from typing import Any

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

logger = logging.getLogger("invigilo.accounts.tasks")

User = get_user_model()


@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=600)
def send_verification_email(self: Any, user_id: str, token: str) -> str:  # type: ignore[no-untyped-def]
    """Send the verification email."""
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("send_verification_email: user %s not found", user_id)
        return "missing_user"

    link = f"{settings.APP_URL}/auth/verify?token={token}"
    send_mail(
        subject="Verify your INVIGILO account",
        message=(
            f"Hi {user.full_name},\n\n"
            f"Please confirm your email by opening the link below:\n\n{link}\n\n"
            "This link expires in 30 minutes."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    return "sent"


@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=600)
def send_password_reset_email(self: Any, user_id: str, token: str) -> str:  # type: ignore[no-untyped-def]
    """Send the password-reset email."""
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("send_password_reset_email: user %s not found", user_id)
        return "missing_user"

    link = f"{settings.APP_URL}/auth/reset?token={token}"
    send_mail(
        subject="Reset your INVIGILO password",
        message=(
            f"Hi {user.full_name},\n\n"
            f"Use the link below to set a new password. If you did not request this, ignore the email.\n\n{link}\n\n"
            "This link expires in 30 minutes."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    return "sent"


@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=600)
def send_login_otp_email(self: Any, user_id: str, code: str) -> str:  # type: ignore[no-untyped-def]
    """Send the login OTP code to the user's email.

    The 6-digit code is the only secret; the user types it on the
    second step of the admin login flow. We do not include a
    clickable link because the whole point of OTP is the user
    manually copying the code from their inbox into the app.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("send_login_otp_email: user %s not found", user_id)
        return "missing_user"

    send_mail(
        subject="Your INVIGILO login code",
        message=(
            f"Hi {user.full_name},\n\n"
            f"Your one-time login code is: {code}\n\n"
            "Enter this code on the login screen to continue. "
            "It expires in 10 minutes and can only be used once.\n\n"
            "If you did not request this code, please change your password immediately."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    return "sent"


__all__ = ["send_login_otp_email", "send_password_reset_email", "send_verification_email"]
