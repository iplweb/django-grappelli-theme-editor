import pytest
from django.core.exceptions import ValidationError

from grappelli_theme_editor.components import (
    component_rules,
    css_string,
    glyph_svg,
    validate_components,
    validate_glyph,
)
from grappelli_theme_editor.css import render_theme_css
from grappelli_theme_editor.models import Theme, ThemeFont
from grappelli_theme_editor.validators import validate_stylesheet_url
from grappelli_theme_editor.webfonts import families_in, web_font_url


@pytest.mark.parametrize("glyph", ["💾", "🗑️", "[+]", "✚", "›"])
def test_valid_glyphs(glyph):
    assert validate_glyph(glyph) == glyph


@pytest.mark.parametrize("glyph", ["", "x" * 9, '"', "a}b", "\\", "<b>", "‮", "a\nb"])
def test_invalid_glyphs(glyph):
    with pytest.raises(ValidationError):
        validate_glyph(glyph)


def test_glyph_is_fully_escaped():
    assert css_string("💾") == '"\\1f4be "'
    svg = glyph_svg("&")
    assert "%26amp%3B" in svg  # XML-escaped, then URL-encoded
    assert '"' not in svg[5:-2] and "'" not in svg[5:-2]


def rules_text(components):
    return "\n".join(f"{s}{{{d}}}" for s, d in component_rules(components))


def test_icon_defaults_emit_nothing():
    assert validate_components({"icons": {"add_icon": "grappelli"}}) == {}


def test_add_icon_custom_and_hidden_search():
    css = rules_text(
        validate_components(
            {
                "icons": {
                    "add_icon": "custom",
                    "add_glyph": "＋",
                    "search_icon": "hidden",
                }
            }
        )
    )
    assert '.grp-object-tools a.grp-add-link::before{content:"\\ff0b "' in css
    assert ".grp-search-button{display:none}" in css


def test_custom_choice_uses_default_glyph():
    css = rules_text(validate_components({"icons": {"search_icon": "custom"}}))
    assert "\\1f50d" in css  # 🔍, the default glyph


def test_submit_icon_only():
    css = rules_text(validate_components({"icons": {"submit_style": "icon_only"}}))
    assert ".grp-submit-row input[name=_save]" in css
    assert "color:transparent" in css
    assert "data:image/svg+xml" in css
    assert ".grp-submit-row a.grp-delete-link{display:inline-flex" in css
    assert "justify-content:center;font-size:0" in css


def test_stylesheet_url_validation():
    validate_stylesheet_url(
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap"
    )
    for bad in ("http://x/y.css", 'https://x/");}', "https://x/a b"):
        with pytest.raises(ValidationError):
            validate_stylesheet_url(bad)


def test_google_font_helpers():
    assert families_in("\"Open Sans\", 'Fira Code', serif") == [
        "Open Sans",
        "Fira Code",
        "serif",
    ]
    assert web_font_url("open sans").startswith(
        "https://fonts.bunny.net/css2?family=Open+Sans:wght@"
    )
    assert web_font_url("Comic Sans MS") is None


@pytest.mark.django_db
def test_theme_imports_only_the_web_fonts_it_uses():
    css = render_theme_css(Theme(name="w", font_sans='"Inter", sans-serif'))
    assert css.startswith('@import url("https://fonts.bunny.net/css2?family=Inter')
    assert "Roboto" not in css
    assert "@import" not in render_theme_css(Theme(name="n", font_sans="Georgia"))


@pytest.mark.django_db
def test_web_fonts_can_be_disabled(settings):
    settings.GRAPPELLI_THEME_EDITOR = {"ALLOW_WEB_FONTS": False}
    css = render_theme_css(Theme(name="w", font_sans='"Inter", sans-serif'))
    assert "@import" not in css


@pytest.mark.django_db
def test_theme_font_needs_exactly_one_source():
    with pytest.raises(ValidationError):
        ThemeFont(family="Nothing").full_clean()
    font = ThemeFont(
        family="Brand",
        stylesheet_url="https://example.com/brand.css",
    )
    font.full_clean()
    font.save()
    css = render_theme_css(Theme(name="b", font_sans='"Brand", sans-serif'))
    assert '@import url("https://example.com/brand.css");' in css


@pytest.mark.django_db
def test_providers(settings):
    assert web_font_url("Inter").startswith("https://fonts.bunny.net/css2?family=")
    assert web_font_url("Inter", "google").startswith("https://fonts.googleapis.com/")
    google = render_theme_css(
        Theme(name="g", font_sans='"Inter", sans-serif', web_font_provider="google")
    )
    assert "fonts.googleapis.com" in google and "bunny" not in google
    settings.GRAPPELLI_THEME_EDITOR = {"WEB_FONT_PROVIDERS": ["bunny"]}
    assert web_font_url("Inter", "google") is None


@pytest.mark.django_db
def test_heading_label_field_fonts():
    css = render_theme_css(
        Theme(
            name="t",
            font_heading='"Lora", serif',
            font_label="Georgia, serif",
            font_field="ui-monospace, monospace",
        )
    )
    assert ".grp-module h2" in css and 'font-family:"Lora", serif !important' in css
    assert "font-family:Georgia, serif !important" in css
    assert "font-family:ui-monospace, monospace !important" in css
    assert "family=Lora" in css  # web font imported


@pytest.mark.django_db
def test_empty_area_patterns():
    css = render_theme_css(
        Theme(
            name="p",
            components={
                "tables": {
                    "empty_pattern": "stripes_left",
                    "empty_color": {"light": "#ff0000"},
                    "empty_size": 20,
                }
            },
        )
    )
    assert ".grp-changelist-results{background:repeating-linear-gradient(-45deg" in css
    assert "20px" in css
    assert "--gte-tables-empty_color:#ff0000" in css


@pytest.mark.django_db
def test_image_url_validation():
    with pytest.raises(ValidationError):
        validate_components({"tables": {"empty_image": 'https://x/a.png") ;'}})
    ok = validate_components({"tables": {"empty_image": "/media/tile.png"}})
    assert ok == {"tables": {"empty_image": "/media/tile.png"}}


@pytest.mark.django_db
def test_page_background_image(tmp_path, settings):
    from django.core.files.base import ContentFile

    settings.MEDIA_ROOT = tmp_path
    theme = Theme(name="img", components={"general": {"page_image": "bottom_right"}})
    theme.image.save("logo.png", ContentFile(b"\x89PNG"), save=False)
    css = render_theme_css(theme)
    assert 'body{background:url("/media/grappelli_theme_editor/images/logo' in css
    assert "no-repeat 100% 100% / auto scroll" in css
    # without an image the option does nothing
    assert "body{background" not in render_theme_css(
        Theme(name="n", components={"general": {"page_image": "tile"}})
    )


def test_line_icons_and_image_urls():
    css = rules_text(
        validate_components(
            {
                "icons": {
                    "add_icon": "line",
                    "search_icon": "line",
                    "submit_style": "icon_text",
                    "submit_icons": "dark",
                    "save_image": "/media/icons/save.png",
                }
            }
        )
    )
    assert "stroke%3D%27%23222222%27" in css  # dark outline icons
    assert 'url("/media/icons/save.png")' in css  # the image wins for Save
    assert ".grp-object-tools a.grp-add-link::before" in css
    assert ".grp-search-button{background:url(" in css


@pytest.mark.django_db
def test_footer_positions_and_modules_leave_the_footer_alone():
    css = render_theme_css(
        Theme(
            name="f",
            components={
                "footer": {"position": "dock"},
                "modules": {"spacing": 20, "radius": 9},
            },
        )
    )
    assert ".grp-fixed-footer{left:50% !important" in css
    assert ".grp-module:not(.grp-submit-row){border-radius:9px" in css
    assert ".grp-module,.grp-group{margin-bottom" not in css
