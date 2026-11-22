"""Curated web fonts offered in the font picker.

A theme whose font list names one of these families gets an ``@import`` of
the provider's stylesheet (when ``ALLOW_WEB_FONTS`` is on):

* ``bunny`` — Bunny Fonts, an EU-hosted drop-in replacement for the Google
  Fonts API that, per bunny.net, does not log visitors' IPs (the default);
* ``google`` — Google Fonts; every visitor's browser contacts Google.

Each theme stores which provider its web fonts come from. Any other web font
(Adobe Fonts kit, Fontsource on jsDelivr, a company CDN…) can be added as a
``ThemeFont`` with a stylesheet URL.

Either way it is a third-party server; the editor says so next to each web
font. Upload font files for fully self-hosted fonts.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from . import conf

PROVIDERS = {
    "bunny": ("Bunny Fonts", "https://fonts.bunny.net"),
    "google": ("Google Fonts", "https://fonts.googleapis.com"),
}


def allowed_providers() -> list[str]:
    """Providers offered in the picker, in display order."""
    if not conf.get("ALLOW_WEB_FONTS"):
        return []
    return [p for p in conf.get("WEB_FONT_PROVIDERS") if p in PROVIDERS]


# (family, category, weights)
GOOGLE_FONTS: list[tuple[str, str, str]] = [
    ("Inter", "sans-serif", "400;500;600;700"),
    ("Roboto", "sans-serif", "400;500;700"),
    ("Open Sans", "sans-serif", "400;600;700"),
    ("Lato", "sans-serif", "400;700"),
    ("Montserrat", "sans-serif", "400;600;700"),
    ("Source Sans 3", "sans-serif", "400;600;700"),
    ("Noto Sans", "sans-serif", "400;600;700"),
    ("Nunito", "sans-serif", "400;600;700"),
    ("Poppins", "sans-serif", "400;500;600"),
    ("Work Sans", "sans-serif", "400;500;600"),
    ("IBM Plex Sans", "sans-serif", "400;500;600"),
    ("Fira Sans", "sans-serif", "400;500;600"),
    ("Rubik", "sans-serif", "400;500;600"),
    ("Manrope", "sans-serif", "400;600;700"),
    ("DM Sans", "sans-serif", "400;500;700"),
    ("Space Grotesk", "sans-serif", "400;500;700"),
    ("Ubuntu", "sans-serif", "400;500;700"),
    ("PT Sans", "sans-serif", "400;700"),
    ("Merriweather", "serif", "400;700"),
    ("Lora", "serif", "400;600;700"),
    ("Source Serif 4", "serif", "400;600;700"),
    ("Playfair Display", "serif", "400;600;700"),
    ("JetBrains Mono", "monospace", "400;600"),
    ("Fira Code", "monospace", "400;600"),
    ("IBM Plex Mono", "monospace", "400;600"),
]
GOOGLE_FONT_NAMES = {name.lower(): (name, cat, w) for name, cat, w in GOOGLE_FONTS}


def web_font_url(family: str, provider: str = "bunny") -> str | None:
    """Stylesheet URL of a curated family at a provider (Google-compatible API)."""
    entry = GOOGLE_FONT_NAMES.get(family.lower())
    if entry is None or provider not in allowed_providers():
        return None
    name, _category, weights = entry
    base = PROVIDERS[provider][1]
    return f"{base}/css2?family={quote_plus(name)}:wght@{weights}&display=swap"


def font_stack(family: str) -> str:
    """CSS font-family value for a picked family, with a generic fallback."""
    entry = GOOGLE_FONT_NAMES.get(family.lower())
    category = entry[1] if entry else "sans-serif"
    return f'"{family}", {category}'


def families_in(font_family: str) -> list[str]:
    """Family names in a CSS font-family list, quotes stripped."""
    return [
        part.strip().strip("\"'")
        for part in (font_family or "").split(",")
        if part.strip()
    ]
