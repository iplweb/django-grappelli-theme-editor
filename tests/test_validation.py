import pytest
from django.core.exceptions import ValidationError

from grappelli_theme_editor.components import validate_components
from grappelli_theme_editor.models import Theme
from grappelli_theme_editor.validators import (
    validate_css_color,
    validate_font_family,
    validate_seeds,
    validate_token_overrides,
)


@pytest.mark.parametrize(
    "value",
    [
        "red;}body{display:none",
        "url(https://evil.example/x)",
        "#fff}",
        "expression(alert(1))",
        "</style><script>",
        "#fff\\9",
    ],
)
def test_colour_injection_is_rejected(value):
    with pytest.raises(ValidationError):
        validate_css_color(value)


@pytest.mark.parametrize("value", ["#fff", "#a1b2c3", "rgb(1, 2, 3)", "rebeccapurple"])
def test_valid_colours(value):
    validate_css_color(value)


@pytest.mark.parametrize(
    "value", ["Inter;} body{", 'Inter, sans-serif"', "a{b}", "url(x)"]
)
def test_font_family_injection_is_rejected(value):
    with pytest.raises(ValidationError):
        validate_font_family(value)


def test_font_family_with_quotes_is_fine():
    validate_font_family("'Segoe UI', \"Helvetica Neue\", sans-serif")


def test_unknown_token_is_rejected():
    with pytest.raises(ValidationError):
        validate_token_overrides({"--grp-nope": "#fff"})


def test_image_tokens_cannot_be_overridden():
    with pytest.raises(ValidationError):
        validate_token_overrides({"--grp-spritesheet": "#fff"})


def test_seed_validation():
    validate_seeds({"light": {"accent": "#123456"}, "dark": {}})
    with pytest.raises(ValidationError):
        validate_seeds({"light": {"bogus": "#123456"}})
    with pytest.raises(ValidationError):
        validate_seeds({"sepia": {}})


def test_components_drop_defaults_and_keep_changes():
    cleaned = validate_components(
        {
            "buttons": {"radius": "5", "height": "32", "surface": "gradient"},
            "navbar": {"background": {"light": "#123456"}},
        }
    )
    assert cleaned == {
        "buttons": {"height": 32},
        "navbar": {"background": {"light": "#123456"}},
    }


@pytest.mark.parametrize(
    "value",
    [
        {"nope": {}},
        {"buttons": {"nope": 1}},
        {"buttons": {"radius": 999}},
        {"buttons": {"radius": "x"}},
        {"buttons": {"shadow": "giant"}},
        {"navbar": {"background": {"light": "red;}"}}},
    ],
)
def test_components_reject_bad_input(value):
    with pytest.raises(ValidationError):
        validate_components(value)


@pytest.mark.django_db
def test_model_clean_normalises_components():
    theme = Theme(name="x", components={"buttons": {"radius": "12"}})
    theme.full_clean()
    assert theme.components == {"buttons": {"radius": 12}}


def test_redos_resistant_and_strict_names():
    import time

    from grappelli_theme_editor import colors

    start = time.monotonic()
    assert not colors.is_valid_css_color("rgb(" + " " * 30 + "1" + " " * 30 + ",2,3")
    assert not colors.is_valid_css_color("rgb(1" + ", " * 5000)
    assert time.monotonic() - start < 0.5
    assert not colors.is_valid_css_color("bananacolor")
    assert colors.is_valid_css_color("RebeccaPurple")


def test_choice_rejects_non_strings():
    with pytest.raises(ValidationError):
        validate_components({"icons": {"add_icon": ["custom"]}})


@pytest.mark.django_db
def test_light_only_component_colour_does_not_leak_into_dark():
    from grappelli_theme_editor.css import render_theme_css

    css = render_theme_css(
        Theme(name="x", components={"tables": {"empty_color": {"light": "#ff0000"}}})
    )
    assert "html[data-theme=dark]{--gte-tables-empty_color:initial;}" in css


@pytest.mark.django_db
def test_switching_site_default_through_the_form(admin_client):
    from django.urls import reverse

    a = Theme.objects.create(name="A", is_site_default=True)
    b = Theme.objects.create(name="B")
    url = reverse("admin:grappelli_theme_editor_theme_change", args=[b.pk])
    data = {
        "name": "B",
        "slug": b.slug,
        "color_scheme": "user",
        "is_site_default": "on",
        "seeds": "{}",
        "light_tokens": "{}",
        "dark_tokens": "{}",
        "components": "{}",
        "font_scale": "1.00",
        "radius_scale": "1.00",
        "spacing_scale": "1.00",
    }
    r = admin_client.post(url, data)
    assert r.status_code == 302, r.content[:2000]
    a.refresh_from_db()
    b.refresh_from_db()
    assert b.is_site_default and not a.is_site_default
