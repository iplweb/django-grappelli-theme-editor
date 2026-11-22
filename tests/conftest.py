from __future__ import annotations

import pytest
from django.contrib.auth.models import Permission

from grappelli_theme_editor.models import Theme


@pytest.fixture(autouse=True)
def _clear_cache():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def staff_user(django_user_model):
    """Staff member WITHOUT model permissions (a "regular" admin user)."""
    return django_user_model.objects.create_user(
        username="staff", password="pw", is_staff=True
    )


@pytest.fixture
def staff_client(client, staff_user):
    client.force_login(staff_user)
    return client


@pytest.fixture
def theme_manager(django_user_model):
    user = django_user_model.objects.create_user(
        username="manager", password="pw", is_staff=True
    )
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="grappelli_theme_editor")
    )
    return user


@pytest.fixture
def shared_theme(db):
    return Theme.objects.create(
        name="Shared",
        seeds={"light": {"accent": "#8e44ad"}, "dark": {}},
    )
