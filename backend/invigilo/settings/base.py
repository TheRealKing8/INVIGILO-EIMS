"""Base settings shared by every environment.

The split is::

    base.py  — what every environment needs.
    dev.py   — local development overrides (DEBUG=1, console email, etc).
    test.py  — pytest-django overrides (in-memory email, fast hasher, etc).
    prod.py  — production hardening (DEBUG=0, SMTP, sentry, etc).

Nothing in this file reads from the OS environment directly except via
``django-environ``. That keeps a single source of truth for the variable
names and types.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import environ

# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# ----------------------------------------------------------------------------
# Environment parsing
# ----------------------------------------------------------------------------
env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    DJANGO_CORS_ALLOWED_ORIGINS=(list, ["http://localhost:3000"]),
    EMAIL_USE_TLS=(bool, False),
    PASSWORD_MIN_LENGTH=(int, 12),
    LOCKOUT_THRESHOLD=(int, 5),
    LOCKOUT_DURATION_MINUTES=(int, 15),
    JWT_ACCESS_LIFETIME_MINUTES=(int, 15),
    JWT_REFRESH_LIFETIME_DAYS=(int, 7),
)

# Read from a project-level .env first (so devs can keep secrets out of the
# shell) and from the OS environment afterwards. The .env file is optional.
env_files = [PROJECT_ROOT / ".env", BASE_DIR / ".env"]
for env_file in env_files:
    if env_file.exists():
        environ.Env.read_env(str(env_file))

# ----------------------------------------------------------------------------
# Core
# ----------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-replace-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# INSTALLED_APPS — local apps first, then third-party, then Django defaults.
LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.academic",
    "apps.rooms",
    "apps.exams",
    "apps.invigilators",
    "apps.allocations",
    "apps.incidents",
    "apps.reports",
    "apps.audit",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "django_filters",
    "corsheaders",
    "django_celery_beat",
]

INSTALLED_APPS = [
    "daphne" if False else None,  # placeholder; ASGI uses in-memory channel layer
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    *LOCAL_APPS,
    *THIRD_PARTY_APPS,
]
INSTALLED_APPS = [a for a in INSTALLED_APPS if a is not None]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "invigilo.middleware.request_id.RequestIDMiddleware",
    "invigilo.middleware.audit_context.AuditContextMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "invigilo.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "invigilo.wsgi.application"
ASGI_APPLICATION = "invigilo.asgi.application"

# ----------------------------------------------------------------------------
# Database
# ----------------------------------------------------------------------------
# Three engines are supported, selected via the DB_BACKEND env var:
#
#   * ``postgres`` — PostgreSQL (default; used by production)
#   * ``mysql``    — MySQL / MariaDB (legacy local dev, e.g. XAMPP)
#   * ``sqlite``   — SQLite (used by pytest; can also be a quick dev fallback)
#
# All credentials are read from the environment; sensible defaults match
# a fresh PostgreSQL install so a fresh checkout Just Works.
# ----------------------------------------------------------------------------
_DB_BACKEND = env("DB_BACKEND", default="postgres").lower()

if _DB_BACKEND == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "db.sqlite3"),
        }
    }
elif _DB_BACKEND == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", default="invigilo"),
            "USER": env("POSTGRES_USER", default="invigilo"),
            "PASSWORD": env("POSTGRES_PASSWORD", default="postgres"),
            "HOST": env("POSTGRES_HOST", default="localhost"),
            "PORT": env("POSTGRES_PORT", default="5432"),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
        }
    }
elif _DB_BACKEND == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env("MYSQL_DB", default="invigilo"),
            "USER": env("MYSQL_USER", default="root"),
            "PASSWORD": env("MYSQL_PASSWORD", default=""),
            "HOST": env("MYSQL_HOST", default="127.0.0.1"),
            "PORT": env("MYSQL_PORT", default="3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
                # MariaDB / MySQL 8 collation that supports 4-byte UTF-8
                # (emojis in incident reports, full Unicode in names).
                "init_command": (
                    "SET sql_mode='STRICT_TRANS_TABLES,NO_ZERO_DATE,"
                    "NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'"
                ),
            },
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
        }
    }
else:
    raise RuntimeError(
        f"Unknown DB_BACKEND={_DB_BACKEND!r}. Use 'mysql', 'postgres', or 'sqlite'."
    )

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ----------------------------------------------------------------------------
# Auth — custom user
# ----------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

# Argon2id with parameters recommended by OWASP for 2024.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "apps.accounts.validators.MinimumLengthValidator"},
    {"NAME": "apps.accounts.validators.ComplexityValidator"},
    {"NAME": "apps.accounts.validators.CommonPasswordValidator"},
]

# Password policy
PASSWORD_MIN_LENGTH = env.int("PASSWORD_MIN_LENGTH", default=12)

# Account lockout
LOCKOUT_THRESHOLD = env.int("LOCKOUT_THRESHOLD", default=5)
LOCKOUT_DURATION_MINUTES = env.int("LOCKOUT_DURATION_MINUTES", default=15)

# ----------------------------------------------------------------------------
# Internationalisation
# ----------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TZ", default="UTC")
USE_I18N = True
USE_TZ = True

# ----------------------------------------------------------------------------
# Static / media
# ----------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# ----------------------------------------------------------------------------
# Django REST Framework
# ----------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions_handler.invigilo_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/minute",
        "user": "1000/minute",
    },
}

# ----------------------------------------------------------------------------
# SimpleJWT
# ----------------------------------------------------------------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("JWT_ACCESS_LIFETIME_MINUTES", default=15)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=env.int("JWT_REFRESH_LIFETIME_DAYS", default=7)
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": env("JWT_SIGNING_KEY", default=SECRET_KEY),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_OBTAIN_SERIALIZER": "apps.accounts.serializers.InvigiloTokenObtainPairSerializer",
    "TOKEN_REFRESH_SERIALIZER": "apps.accounts.serializers.InvigiloTokenRefreshSerializer",
    "TOKEN_BLACKLIST_ENABLED": True,
    "JTI_CLAIM": "jti",
    "ISSUER": env("JWT_ISSUER", default="invigilo"),
    "AUDIENCE": "invigilo-api",
}

# ----------------------------------------------------------------------------
# drf-spectacular — OpenAPI
# ----------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "INVIGILO API",
    "DESCRIPTION": "Smart Examination Invigilation Management System",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v1/",
    "TAGS": [
        {"name": "auth", "description": "Authentication, password, email verification."},
        {"name": "users", "description": "User administration."},
        {"name": "health", "description": "Liveness and readiness."},
        {"name": "academic", "description": "Faculties, departments, programs, courses."},
        {"name": "rooms", "description": "Buildings and rooms used as exam venues."},
        {"name": "exams", "description": "Exam periods and individual sessions."},
        {"name": "invigilators", "description": "Invigilator profiles and availability."},
        {"name": "allocations", "description": "Allocation runs, individual allocations, and conflicts."},
        {"name": "incidents", "description": "Incidents reported during exam sessions."},
        {"name": "reports", "description": "Report exports (PDF / Excel / CSV) and downloads."},
        {"name": "audit", "description": "Append-only audit log of consequential writes."},
    ],
}

# ----------------------------------------------------------------------------
# CORS
# ----------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000", "http://localhost:8080"],
)
CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = ["X-Request-ID"]

# ----------------------------------------------------------------------------
# Celery
# ----------------------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://redis:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://redis:6379/2")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# ----------------------------------------------------------------------------
# Redis cache
# ----------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://redis:6379/0"),
    }
}

# ----------------------------------------------------------------------------
# Email
# ----------------------------------------------------------------------------
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="mailhog")
EMAIL_PORT = env.int("EMAIL_PORT", default=1025)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
DEFAULT_FROM_EMAIL = env("EMAIL_FROM", default="noreply@invigilo.local")

# ----------------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "invigilo.logging.JSONFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
        "console": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "invigilo": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}

# ----------------------------------------------------------------------------
# Security headers — sensible defaults; hardened in prod.py
# ----------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
