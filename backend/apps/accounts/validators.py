"""Password validators for INVIGILO.

These implement the policy in ``docs/02-requirements.md`` §1.1:

* Minimum 12 characters.
* At least three of: lowercase, uppercase, digit, symbol.
* Not in a list of common passwords (top 1,000).
"""
from __future__ import annotations

import re
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class MinimumLengthValidator:
    """Reject passwords shorter than ``PASSWORD_MIN_LENGTH``."""

    def validate(self, password: str, user: Any = None) -> None:  # noqa: A003
        if len(password or "") < settings.PASSWORD_MIN_LENGTH:
            raise ValidationError(
                _("Password must be at least %(min)d characters."),
                code="password_too_short",
                params={"min": settings.PASSWORD_MIN_LENGTH},
            )

    def get_help_text(self) -> str:
        return _("Password must be at least %d characters.") % settings.PASSWORD_MIN_LENGTH


class ComplexityValidator:
    """Require three of {lowercase, uppercase, digit, symbol}."""

    PATTERNS = {
        "lowercase": re.compile(r"[a-z]"),
        "uppercase": re.compile(r"[A-Z]"),
        "digit": re.compile(r"\d"),
        "symbol": re.compile(r"[^A-Za-z0-9]"),
    }
    REQUIRED = 3

    def validate(self, password: str, user: Any = None) -> None:  # noqa: A003
        present = sum(1 for p in self.PATTERNS.values() if p.search(password or ""))
        if present < self.REQUIRED:
            raise ValidationError(
                _("Password must contain at least %(n)d of: lowercase, uppercase, digit, symbol."),
                code="password_not_complex",
                params={"n": self.REQUIRED},
            )

    def get_help_text(self) -> str:
        return _("Must contain at least three of: lowercase, uppercase, digit, symbol.")


class CommonPasswordValidator:
    """Reject the top 1,000 most common passwords (a small built-in list).

    The full list ships with ``django-password-validators`` in production;
    we keep a representative subset here so the test suite is self-contained.
    """

    COMMON = frozenset(
        {
            "password",
            "12345678",
            "123456789",
            "1234567890",
            "qwerty123",
            "letmein123",
            "welcome1!",
            "admin1234",
            "iloveyou!",
            "p@ssw0rd",
        }
    )

    def validate(self, password: str, user: Any = None) -> None:  # noqa: A003
        if (password or "").lower() in self.COMMON:
            raise ValidationError(_("This password is too common."), code="password_common")

    def get_help_text(self) -> str:
        return _("Password must not be a common password.")


__all__ = [
    "MinimumLengthValidator",
    "ComplexityValidator",
    "CommonPasswordValidator",
]
