from decimal import Decimal

import pytest

from grappelli_theme_editor.css import layer_css, render_theme_css
from grappelli_theme_editor.models import Theme, ThemeFont


@pytest.mark.django_db
def test_colour_only_theme_does_not_touch_fonts_or_radii():
    css = render_theme_css(Theme(name="c", seeds={"light": {"accent": "#8e44ad"}}))
    assert "--grp-link-color:#8e44ad" in css
    assert "font-family" not in css
    assert "border-radius" not in css
    assert "/* components */" not in css


@pytest.mark.django_db
def test_values_use_grappelli_selectors():
    css = render_theme_css(
        Theme(name="c", seeds={"light": {}, "dark": {"accent": "#ff8800"}})
    )
    assert "html[data-theme=dark]{" in css
    assert "@media (prefers-color-scheme: dark){html[data-theme=auto]{" in css
    assert ":root{" not in css  # nothing changed in light mode


@pytest.mark.django_db
def test_font_theme_emits_layer_and_variable():
    css = render_theme_css(Theme(name="f", font_sans="Inter, sans-serif"))
    assert "--gte-font-sans:Inter, sans-serif" in css
    assert "font-family:var(--gte-font-sans, Arial,sans-serif)" in css
    assert "border-radius" not in css  # only the parts in use


def test_layer_with_defaults_keeps_grappelli_values():
    layer = layer_css()
    # every scaled length falls back to its original value
    assert "calc(3px * var(--gte-radius-scale, 1))" in layer
    assert "calc(12px * var(--gte-font-scale, 1))" in layer
    # the header offset padding is not scaled with density
    assert "#grp-content{padding:calc(80px" not in layer


@pytest.mark.django_db
def test_scales_are_emitted():
    css = render_theme_css(
        Theme(
            name="s",
            font_scale=Decimal("1.10"),
            radius_scale=Decimal("0"),
            spacing_scale=Decimal("0.8"),
        )
    )
    assert "--gte-font-scale:1.1" in css
    assert "--gte-radius-scale:0" in css
    assert "--gte-spacing-scale:0.8" in css
    # font size/density change the fixed header's height
    assert "var(--gte-header-height" in css


@pytest.mark.django_db
def test_forced_dark_theme_overrides_everything_everywhere():
    css = render_theme_css(Theme(name="d", color_scheme="dark"))
    assert ":root,html[data-theme=dark]{" in css
    assert "color-scheme:dark" in css
    assert ".theme-toggle{display:none}" in css
    # image tokens are rewritten to absolute static URLs
    assert 'url("/static/grappelli/images/' in css


@pytest.mark.django_db
def test_components_are_important_and_flatten_gradients():
    css = render_theme_css(
        Theme(
            name="k",
            components={
                "buttons": {"radius": 12, "surface": "flat"},
                "navbar": {"padding_y": 18},
            },
        )
    )
    assert "border-radius:12px !important" in css
    assert (
        "--grp-form-button-gradient-from:var(--grp-form-button-background-color)" in css
    )
    assert "h1#grp-admin-title{padding-top:18px !important" in css
    assert "padding-top:calc(var(--gte-header-height, 62px) + 18px)" in css


@pytest.mark.django_db
def test_component_colour_falls_back_per_mode():
    css = render_theme_css(
        Theme(name="n", components={"navbar": {"background": {"light": "#123456"}}})
    )
    assert ":root{--gte-navbar-background:#123456;}" in css
    assert "var(--gte-navbar-background, linear-gradient(" in css


@pytest.mark.django_db
def test_static_header_option():
    css = render_theme_css(
        Theme(name="h", components={"navbar": {"position": "static"}})
    )
    assert "header#grp-header{position:relative !important" in css


@pytest.mark.django_db
def test_custom_css_is_appended():
    css = render_theme_css(Theme(name="x", custom_css="body{outline:1px red}"))
    assert css.rstrip().endswith("body{outline:1px red}")


@pytest.mark.django_db
def test_font_faces(tmp_path, settings):
    from django.core.files.base import ContentFile

    settings.MEDIA_ROOT = tmp_path
    font = ThemeFont(family="Inter", weight=600)
    font.file.save("inter.woff2", ContentFile(b"wOF2"), save=True)
    css = render_theme_css(Theme(name="f", font_sans='"Inter", sans-serif'))
    assert '@font-face{font-family:"Inter";' in css
    assert 'format("woff2")' in css
    assert "font-weight:600" in css
