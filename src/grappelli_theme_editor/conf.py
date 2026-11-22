"""Package settings, read from the ``GRAPPELLI_THEME_EDITOR`` dict."""

from __future__ import annotations

from typing import Any

from django.conf import settings

DEFAULTS: dict[str, Any] = {
    # Let staff users without model permissions build private themes for
    # themselves on the "My theme" page. Choosing a shared theme is always
    # allowed.
    "ALLOW_USER_THEMES": True,
    # Allow ThemeFont entries that link a web font stylesheet (e.g. Google
    # Fonts). Visitors' browsers then contact that server; disable if your
    # privacy policy forbids it — uploaded font files are always allowed.
    "ALLOW_WEB_FONTS": True,
    # Web font services offered in the editor, in this order: "bunny"
    # (fonts.bunny.net, EU-hosted, no IP logging per bunny.net), "google".
    "WEB_FONT_PROVIDERS": ["bunny", "google"],
    # Seconds the rendered CSS is kept in Django's cache. The URL is
    # versioned, so a stale cache entry is never served for a newer theme.
    "CACHE_TIMEOUT": 60 * 60 * 24,
    # Add a "My theme" link to Grappelli's user tools (needs the bundled
    # admin/base_site.html, see README).
    "USER_TOOLS_LINK": True,
    # Max. size of an uploaded font file, in bytes.
    "MAX_FONT_SIZE": 2 * 1024 * 1024,
    # Max. size of a theme's background image, in bytes.
    "MAX_IMAGE_SIZE": 512 * 1024,
}


def get(name: str) -> Any:
    user = getattr(settings, "GRAPPELLI_THEME_EDITOR", {}) or {}
    return user.get(name, DEFAULTS[name])
