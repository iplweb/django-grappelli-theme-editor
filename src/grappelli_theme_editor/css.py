"""Render a Theme into a stylesheet that is loaded after Grappelli's own.

The output has three parts:

1. ``@font-face`` rules for every uploaded :class:`ThemeFont`;
2. the *layer*: rules re-declaring Grappelli's hardcoded font families,
   font sizes and corner radii in terms of ``--gte-*`` variables, with
   fallbacks equal to Grappelli's defaults (so the layer alone changes
   nothing). Only the parts a theme uses are emitted;
3. the theme's values: ``--grp-*`` and ``--gte-*`` variables, emitted under
   the very selectors Grappelli uses (``:root``, ``html[data-theme=dark]``
   and the ``prefers-color-scheme`` block for ``data-theme=auto``), plus
   the superuser-only custom CSS.

Because the sheet comes after ``screen.css`` and repeats the same
selectors, plain source order makes it win — no ``!important`` needed.
"""

from __future__ import annotations

import hashlib
import re
from functools import cache

from django.core.cache import cache as django_cache
from django.templatetags.static import static

from . import conf, tokens_data
from .components import (
    HEADER_MEASURED_RULES,
    HEADER_STATIC_RULES,
    component_rules,
    component_variables,
    flattened_tokens,
)
from .models import Theme, ThemeFont
from .palette import derive_tokens
from .tokens import DARK, LIGHT, all_tokens
from .webfonts import families_in, web_font_url

SANS_DEFAULT = "Arial,sans-serif"
MONO_DEFAULT = '"Bitstream Vera Sans Mono",Monaco,"Courier New",Courier,monospace'

LIGHT_SELECTOR = ":root"
DARK_SELECTOR = "html[data-theme=dark]"
AUTO_DARK_BLOCK = "@media (prefers-color-scheme: dark){html[data-theme=auto]{%s}}"


PX_RE = re.compile(r"^(\d+(?:\.\d+)?)px$")

# Layer parts; a theme only emits the parts it actually changes, so a
# colour-only theme never re-declares fonts or radii (which could clobber
# the host project's own font CSS).
SANS = "sans"
MONO = "mono"
SIZE = "size"
RADIUS = "radius"
SPACING = "spacing"
ALL_PARTS = frozenset({SANS, MONO, SIZE, RADIUS, SPACING})

_PX_ANY_RE = re.compile(r"(?<![\w.-])(\d+(?:\.\d+)?)px")
# Paddings that are layout offsets rather than spacing (the 80px gap below
# Grappelli's fixed header) must not scale with density.
_SPACING_SKIP_RE = re.compile(r"#grp-content(?![\w-])")


def _scaled(value: str, var: str) -> str:
    if PX_RE.match(value):
        return f"calc({value} * var({var}, 1))"
    return value


def _scaled_all(value: str, var: str) -> str:
    """Scale every px length in a shorthand like ``5px 10px 0``."""
    return _PX_ANY_RE.sub(lambda m: f"calc({m.group(0)} * var({var}, 1))", value)


def _family(value: str, parts: frozenset[str]) -> str | None:
    if value.replace(" ", "") == SANS_DEFAULT and SANS in parts:
        return f"var(--gte-font-sans, {SANS_DEFAULT})"
    if "monospace" in value and MONO in parts:
        return f"var(--gte-font-mono, {value})"
    return value


def _join(entries: list[tuple[str, str, str]]) -> str:
    """Emit (media, selector, declaration) in order, merging media runs."""
    out: list[str] = []

    def flush(media: str, run: list[str]) -> None:
        if run:
            body = "".join(run)
            out.append(f"{media}{{{body}}}" if media else body)

    run_media, run = "", []
    for media, selector, decl in entries:
        if media != run_media:
            flush(run_media, run)
            run_media, run = media, []
        run.append(f"{selector}{{{decl}}}")
    flush(run_media, run)
    return "\n".join(out)


@cache
def layer_css(parts: frozenset[str] = ALL_PARTS) -> str:
    """Rules re-declaring hardcoded fonts/sizes/radii through ``--gte-*``.

    All declarations of a property are replayed in Grappelli's source order
    (also the untouched ones) so the cascade among them is unchanged; with
    the variables unset the result is pixel-identical to stock Grappelli.
    """
    sections = []
    if parts & {SANS, MONO}:
        sections.append(
            _join(
                [
                    (m, s, f"font-family:{_family(v, parts)}")
                    for m, s, v in tokens_data.FONT_FAMILY_DECLS
                ]
            )
        )
    if SIZE in parts:
        sections.append(
            _join(
                [
                    (m, s, f"font-size:{_scaled(v, '--gte-font-scale')}")
                    for m, s, v in tokens_data.FONT_SIZE_DECLS
                ]
            )
        )
    if RADIUS in parts:
        sections.append(
            _join(
                [
                    (m, s, f"{p}:{_scaled(v, '--gte-radius-scale')}")
                    for m, s, p, v in tokens_data.RADIUS_DECLS
                ]
            )
        )
    if SPACING in parts:
        sections.append(
            _join(
                [
                    (m, s, f"{p}:{_scaled_all(v, '--gte-spacing-scale')}")
                    for m, s, p, v in tokens_data.PADDING_DECLS
                    if not _SPACING_SKIP_RE.search(s)
                ]
            )
        )
    if not sections:
        return ""
    return "/* grappelli-theme-editor layer */\n" + "\n".join(sections)


def theme_layer_parts(theme: Theme) -> frozenset[str]:
    parts = set()
    if theme.font_sans:
        parts.add(SANS)
    if theme.font_mono:
        parts.add(MONO)
    if theme.font_scale != 1:
        parts.add(SIZE)
    if theme.radius_scale != 1:
        parts.add(RADIUS)
    if theme.spacing_scale != 1:
        parts.add(SPACING)
    return frozenset(parts)


def font_imports_css(families: list[str] | None = None, provider: str = "bunny") -> str:
    """@import rules for web fonts; must come first in the stylesheet.

    ``families`` limits the imports to the fonts a theme actually uses
    (``None`` = every ThemeFont web font). A family resolves to a ThemeFont
    with a stylesheet URL first, then to the curated list at ``provider``.
    """
    if not conf.get("ALLOW_WEB_FONTS"):
        return ""
    known = {
        family.lower(): url
        for family, url in ThemeFont.objects.exclude(stylesheet_url="").values_list(
            "family", "stylesheet_url"
        )
    }
    urls: list[str] = []
    wanted = families if families is not None else list(known)
    for family in wanted:
        url = known.get(family.lower()) or web_font_url(family, provider)
        if url and url not in urls:
            urls.append(url)
    return "\n".join(f'@import url("{url}");' for url in urls)


def font_faces_css() -> str:
    rules = []
    for font in ThemeFont.objects.exclude(file=""):
        rules.append(
            "@font-face{"
            f'font-family:"{font.family}";'
            f'src:url("{font.file.url}") format("{font.css_format}");'
            f"font-weight:{font.weight};font-style:{font.style};"
            "font-display:swap}"
        )
    return "\n".join(rules)


def _absolute_image(value: str) -> str:
    """Grappelli's image tokens are relative to its own stylesheet."""
    inner = value.strip()[4:-1].strip().strip("\"'")
    path = inner.removeprefix("../")
    return f'url("{static("grappelli/" + path)}")'


def theme_variables(theme: Theme, mode: str) -> dict[str, str]:
    """All variables the theme sets for ``mode`` (``--grp-*`` and ``--gte-*``)."""
    out = derive_tokens(theme.seeds, mode)
    out.update(_flattened(theme.components))
    out.update(theme.tokens_for(mode) or {})
    out.update(component_variables(theme.components, mode))
    if theme.font_sans:
        out["--gte-font-sans"] = theme.font_sans
    if theme.font_mono:
        out["--gte-font-mono"] = theme.font_mono
    if theme.font_scale != 1:
        out["--gte-font-scale"] = format(theme.font_scale.normalize(), "f")
    if theme.radius_scale != 1:
        out["--gte-radius-scale"] = format(theme.radius_scale.normalize(), "f")
    if theme.spacing_scale != 1:
        out["--gte-spacing-scale"] = format(theme.spacing_scale.normalize(), "f")
    return out


def _flattened(components: dict) -> dict[str, str]:
    """Turn gradients into flat fills by pointing gradient stops at one colour."""
    known = all_tokens()
    out = {}
    for name in flattened_tokens(components):
        to = name.replace("gradient-from", "gradient-to")
        bg = name.replace("gradient-from", "background-color")
        if to in known:
            out[name] = f"var({to})"
        elif bg in known:
            out[name] = f"var({bg})"
    return out


HEADING_SELECTORS = (
    "h1,h2,h3,h4,#grp-content-title h1,h1#grp-admin-title,"
    ".grp-module h2,.grp-module h3,.grp-module h4,.grp-group>h2,"
    "body.grp-login .grp-module-login h1"
)
LABEL_SELECTORS = (
    "label,legend,fieldset.grp-module .grp-row label,"
    "fieldset.grp-module .grp-row legend,.grp-filter .grp-row label,"
    "table.grp-table thead th"
)
FIELD_SELECTORS = (
    "input[type=text],input[type=password],input[type=url],input[type=email],"
    "input[type=number],input[type=search],textarea,select,"
    ".select2-container .select2-selection,.select2-search__field"
)


def typography_rules(theme: Theme) -> list[tuple[str, str]]:
    """Per-element fonts (headings, labels, form fields)."""
    rules = []
    for value, selectors in (
        (theme.font_heading, HEADING_SELECTORS),
        (theme.font_label, LABEL_SELECTORS),
        (theme.font_field, FIELD_SELECTORS),
    ):
        if value:
            rules.append((selectors, f"font-family:{value}"))
    return rules


def split_declarations(decls: str) -> list[str]:
    """Split on ``;`` outside quotes and brackets (data: URIs contain ``;``)."""
    parts, depth, quote, start = [], 0, "", 0
    for i, ch in enumerate(decls):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == ";" and depth == 0:
            parts.append(decls[start:i])
            start = i + 1
    parts.append(decls[start:])
    return parts


def components_css(theme: Theme, image_url: str | None = None) -> str:
    if image_url is None and theme.image:
        image_url = theme.image.url
    rules = typography_rules(theme) + component_rules(
        theme.components, {"image_url": image_url}
    )
    header_handled = any(
        r in HEADER_MEASURED_RULES or r in HEADER_STATIC_RULES for r in rules
    )
    if not header_handled and (theme.spacing_scale != 1 or theme.font_scale != 1):
        # Density and font size change the fixed header's height too.
        rules.extend(HEADER_MEASURED_RULES)
    if not rules:
        return ""
    body = []
    for selector, decls in rules:
        important = ";".join(
            f"{d.strip()} !important" for d in split_declarations(decls) if d.strip()
        )
        body.append(f"{selector}{{{important}}}")
    return "/* components */\n" + "\n".join(body)


def _forced_variables(theme: Theme, mode: str) -> dict[str, str]:
    """Complete variable set for a theme pinned to one mode.

    A pinned theme must override *every* token in every selector, otherwise
    Grappelli's dark block would still win for the untouched ones.
    """
    out = {}
    for name, token in all_tokens().items():
        value = token.default(mode)
        out[name] = _absolute_image(value) if token.kind == "image" else value
    out.update(theme_variables(theme, mode))
    return out


def _decls(variables: dict[str, str], extra: str = "") -> str:
    return "".join(f"{k}:{v};" for k, v in sorted(variables.items())) + extra


def theme_values_css(theme: Theme) -> str:
    if theme.color_scheme in (Theme.ColorScheme.LIGHT, Theme.ColorScheme.DARK):
        mode = LIGHT if theme.color_scheme == Theme.ColorScheme.LIGHT else DARK
        body = _decls(_forced_variables(theme, mode), f"color-scheme:{mode}")
        return (
            f"{LIGHT_SELECTOR},{DARK_SELECTOR}{{{body}}}\n"
            + AUTO_DARK_BLOCK % body
            + "\n.theme-toggle{display:none}"
        )
    light = _decls(theme_variables(theme, LIGHT))
    dark = _decls(theme_variables(theme, DARK))
    parts = []
    if light:
        parts.append(f"{LIGHT_SELECTOR}{{{light}}}")
    if dark:
        parts.append(f"{DARK_SELECTOR}{{{dark}}}")
        parts.append(AUTO_DARK_BLOCK % dark)
    return "\n".join(parts)


def render_theme_css(theme: Theme | None, image_url: str | None = None) -> str:
    """Full stylesheet for ``theme``.

    ``None`` renders the font faces plus the complete layer. ``image_url``
    overrides the theme's uploaded image (the preview passes a data: URI of
    a not-yet-saved upload).
    """
    if theme is None:
        sections = [font_imports_css(), font_faces_css(), layer_css(ALL_PARTS)]
    else:
        parts = theme_layer_parts(theme)
        families = [f for value in theme.font_fields for f in families_in(value)]
        uses_fonts = bool(families)
        sections = [
            font_imports_css(families, theme.web_font_provider) if uses_fonts else "",
            font_faces_css() if uses_fonts else "",
        ]
        sections.append(layer_css(parts))
        sections.append(f"/* theme: {theme.slug} */")
        sections.append(theme_values_css(theme))
        sections.append(components_css(theme, image_url))
        if theme.custom_css.strip():
            sections.append("/* custom CSS */\n" + theme.custom_css)
    return "\n".join(s for s in sections if s) + "\n"


def _fingerprint(theme: Theme) -> str:
    """Everything the rendered stylesheet depends on, as a cache key.

    The theme row, every font (any font can be referenced by name), the
    settings that change the output and the package version.
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        package = version("django-grappelli-theme-editor")
    except PackageNotFoundError:  # running from a source checkout
        package = "dev"
    fonts = list(
        ThemeFont.objects.order_by("pk").values_list(
            "pk", "family", "file", "stylesheet_url", "weight", "style", "updated_at"
        )
    )
    raw = repr(
        (
            package,
            theme.pk,
            theme.updated_at.isoformat() if theme.updated_at else None,
            fonts,
            conf.get("ALLOW_WEB_FONTS"),
            conf.get("WEB_FONT_PROVIDERS"),
        )
    )
    return hashlib.sha1(raw.encode()).hexdigest()


def cached_theme_css_and_version(theme: Theme) -> tuple[str, str]:
    """(css, version) where version is a hash of the CSS bytes themselves."""
    key = f"grappelli_theme_editor:css:{theme.pk}:{_fingerprint(theme)}"
    hit = django_cache.get(key)
    if hit is None:
        css = render_theme_css(theme)
        hit = (css, hashlib.sha1(css.encode()).hexdigest()[:12])
        django_cache.set(key, hit, conf.get("CACHE_TIMEOUT"))
    return hit
