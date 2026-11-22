"""Test settings: Postgres from a testcontainer (started at import time).

Set ``GTE_TEST_SQLITE=1`` to run against in-memory SQLite instead (no
Docker needed; the package uses nothing Postgres-specific).
"""

from __future__ import annotations

import atexit
import os

SECRET_KEY = "grappelli-theme-editor-tests-not-secret"
DEBUG = False
ALLOWED_HOSTS = ["*"]

if os.environ.get("GTE_TEST_SQLITE") == "1":
    DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
    }
else:
    from testcontainers.postgres import PostgresContainer

    _postgres = PostgresContainer("postgres:17-alpine")
    _postgres.start()
    atexit.register(_postgres.stop)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _postgres.dbname,
            "USER": _postgres.username,
            "PASSWORD": _postgres.password,
            "HOST": _postgres.get_container_host_ip(),
            "PORT": _postgres.get_exposed_port(5432),
        }
    }

INSTALLED_APPS = [
    "grappelli_theme_editor",
    "grappelli",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Optional integration, enabled in the test suite.
    "reversion",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "tests.urls"

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
    }
]

STATIC_URL = "/static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(os.path.dirname(__file__), "_media")
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
