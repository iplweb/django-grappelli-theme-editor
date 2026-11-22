import pytest
from django.core.management import call_command

from grappelli_theme_editor.contrast import warnings
from grappelli_theme_editor.css import render_theme_css, theme_variables
from grappelli_theme_editor.models import Theme
from grappelli_theme_editor.views import _checked_modes


@pytest.mark.django_db
def test_presets_load_idempotently():
    call_command("load_theme_presets")
    count = Theme.objects.count()
    assert count >= 5
    call_command("load_theme_presets")
    assert Theme.objects.count() == count


@pytest.mark.django_db
def test_presets_render_and_pass_contrast_checks():
    call_command("load_theme_presets")
    for theme in Theme.objects.all():
        assert render_theme_css(theme)
        problems = warnings(
            {m: theme_variables(theme, m) for m in ("light", "dark")},
            _checked_modes(theme),
        )
        assert problems == [], (theme.slug, problems)
