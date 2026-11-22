"""Settings for the django-grappelli-theme-editor demo.

* ``uv run python manage.py runserver`` — SQLite, works out of the box.
* ``uv run run-site run`` — Postgres testcontainer + autologin (the
  ``[example]`` extra); the sidecar ``.run-site-config`` switches the
  database automatically.
"""

import importlib.util
import os
import tomllib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "demo-not-secret"
DEBUG = True
ALLOWED_HOSTS = ["*"]

_DEV_HELPERS = importlib.util.find_spec("django_dev_helpers") is not None

INSTALLED_APPS = [
    # Must come before grappelli: it overrides admin/base_site.html.
    "grappelli_theme_editor",
    "grappelli",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "demo",
]
if _DEV_HELPERS:
    INSTALLED_APPS.append("django_dev_helpers")
# django-reversion (the [example] extra): undo for themes in the editor.
if importlib.util.find_spec("reversion") is not None:
    INSTALLED_APPS.append("reversion")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "example_project.urls"
WSGI_APPLICATION = "example_project.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]


def _run_site_config():
    sidecar = BASE_DIR / ".run-site-config"
    if not sidecar.is_file():
        return None
    with sidecar.open("rb") as f:
        return tomllib.load(f)


_RS = _run_site_config()
if _RS and "postgres" in _RS:
    pg = _RS["postgres"]
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": pg["db"],
            "USER": pg["user"],
            "PASSWORD": pg["password"],
            "HOST": pg["host"],
            "PORT": str(pg["port"]),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            # GTE_DEMO_DB: use another file, e.g. a fresh one for screenshots.
            "NAME": os.environ.get("GTE_DEMO_DB", BASE_DIR / "db.sqlite3"),
        }
    }

LANGUAGE_CODE = "en-us"
# The demo is English-only; the package itself also ships a Polish catalog.
LANGUAGES = [("en", "English")]
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
GRAPPELLI_ADMIN_TITLE = "Theme editor demo"

if _DEV_HELPERS:
    DJANGO_DEV_HELPERS = {
        "enabled": os.environ.get("DJANGO_DEV_HELPERS_ENABLED", "1") == "1",
    }
