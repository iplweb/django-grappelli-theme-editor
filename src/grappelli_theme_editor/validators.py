"""Validation of user-supplied values that end up inside generated CSS.

Everything a non-superuser can type is interpolated into a stylesheet, so
values are whitelisted rather than escaped: no braces, semicolons, quotes
outside font names, ``url(``, ``@import``, ``expression(`` or backslashes.
"""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from . import colors
from .palette import SEED_KEYS
from .tokens import MODES, color_tokens

_FONT_FAMILY_RE = re.compile(r"^[A-Za-z0-9 ,'\"_\-]{1,200}$")
_FORBIDDEN = ("url(", "expression(", "@import", "\\", "{", "}", ";", "<", ">")


def validate_css_color(value: str) -> None:
    if not isinstance(value, str) or any(f in value.lower() for f in _FORBIDDEN):
        raise ValidationError(_("%(value)r is not a colour.") % {"value": value})
    if not colors.is_valid_css_color(value):
        raise ValidationError(_("%(value)r is not a colour.") % {"value": value})


def validate_font_family(value: str) -> None:
    if not value:
        return
    if not _FONT_FAMILY_RE.match(value) or value.count('"') % 2 or value.count("'") % 2:
        raise ValidationError(
            _(
                "A font family may contain letters, digits, spaces, commas, "
                "hyphens, underscores and paired quotes only."
            )
        )


def validate_token_overrides(value) -> None:
    if not isinstance(value, dict):
        raise ValidationError(_("Token overrides must be a JSON object."))
    known = color_tokens()
    errors = []
    for name, color in value.items():
        if name not in known:
            errors.append(_("Unknown token %(name)s.") % {"name": name})
            continue
        try:
            validate_css_color(color)
        except ValidationError as e:
            errors.append(f"{name}: {e.messages[0]}")
    if errors:
        raise ValidationError(errors)


def validate_seeds(value) -> None:
    if not isinstance(value, dict) or set(value) - set(MODES):
        raise ValidationError(_('Seeds must look like {"light": {}, "dark": {}}.'))
    errors = []
    for mode, seeds in value.items():
        if not isinstance(seeds, dict):
            errors.append(_("Seeds for %(mode)s must be an object.") % {"mode": mode})
            continue
        for key, color in seeds.items():
            if key not in SEED_KEYS:
                errors.append(_("Unknown seed %(key)s.") % {"key": key})
                continue
            try:
                colors.parse(color)
            except (colors.ColorError, AttributeError):
                errors.append(
                    _("%(mode)s/%(key)s: %(value)r is not a colour.")
                    % {"mode": mode, "key": key, "value": color}
                )
    if errors:
        raise ValidationError(errors)


def validate_stylesheet_url(value: str) -> None:
    """A web font stylesheet: https, and nothing that could break @import."""
    if not value:
        return
    if not value.startswith("https://") or any(
        ch in value for ch in ('"', "'", "(", ")", "\\", " ", "<", ">", "\n")
    ):
        raise ValidationError(
            _("Enter an https:// URL of a font stylesheet (no quotes or brackets).")
        )
