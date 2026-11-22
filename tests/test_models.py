import json

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from grappelli_theme_editor.models import Theme


@pytest.mark.django_db
def test_only_one_site_default():
    a = Theme.objects.create(name="A", is_site_default=True)
    b = Theme.objects.create(name="B", is_site_default=True)
    a.refresh_from_db()
    assert not a.is_site_default
    assert b.is_site_default


@pytest.mark.django_db
def test_private_theme_cannot_be_site_default(staff_user):
    theme = Theme(name="mine", owner=staff_user, is_site_default=True)
    with pytest.raises(ValidationError):
        theme.full_clean()
    with pytest.raises(IntegrityError):
        theme.save()


@pytest.mark.django_db
def test_slug_is_generated_and_unique():
    a = Theme.objects.create(name="Dark blue")
    b = Theme.objects.create(name="Dark blue")
    assert a.slug == "dark-blue"
    assert b.slug == "dark-blue-2"


@pytest.mark.django_db
def test_export_import_roundtrip():
    theme = Theme.objects.create(
        name="Round",
        seeds={"light": {"accent": "#112233"}, "dark": {}},
        components={"buttons": {"radius": 9}},
        font_sans="Georgia, serif",
        custom_css="body{}",
    )
    data = json.loads(json.dumps(theme.to_dict()))
    copy = Theme()
    copy.update_from_dict(data, allow_custom_css=False)
    copy.full_clean(exclude=["slug"])
    copy.save()
    assert copy.seeds == theme.seeds
    assert copy.components == theme.components
    assert copy.font_sans == theme.font_sans
    assert copy.custom_css == ""  # not allowed for this importer


@pytest.mark.django_db
def test_version_hash_changes_on_save(shared_theme):
    before = shared_theme.version_hash()
    shared_theme.font_sans = "Verdana"
    shared_theme.save()
    assert shared_theme.version_hash() != before


@pytest.mark.django_db
def test_system_checks_pass():
    from django.core.management import call_command

    call_command("check", fail_level="WARNING")
