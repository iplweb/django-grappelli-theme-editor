"""WCAG contrast warnings for the most important text/background pairs."""

from __future__ import annotations

import re

from django.utils.translation import gettext_lazy as _

from . import colors
from .tokens import MODES, color_tokens

# (foreground, background, what it is, minimum ratio); "a|b" = first defined
PAIRS = [
    ("--grp-font-color", "--grp-body-background-color", _("Body text"), 4.5),
    ("--grp-link-color", "--grp-body-background-color", _("Links"), 4.5),
    ("--grp-font-color", "--grp-module-background-color", _("Text in modules"), 4.5),
    (
        "--grp-form-label-font-color",
        "--grp-module-background-color",
        _("Form labels"),
        4.5,
    ),
    (
        "--grp-form-field-font-color",
        "--grp-form-field-background-color",
        _("Text in form fields"),
        4.5,
    ),
    (
        "--gte-navbar-text|--grp-font-color-inverted",
        "--gte-navbar-background|--grp-dark-background-color",
        _("Top bar title"),
        4.5,
    ),
    (
        "--gte-navbar-link|--grp-link-color-bright",
        "--gte-navbar-background|--grp-dark-background-color",
        _("Top bar links"),
        4.5,
    ),
    (
        "--gte-breadcrumbs-link|--grp-link-color",
        "--gte-breadcrumbs-background|--grp-context-navigation-background-color",
        _("Breadcrumb links"),
        4.5,
    ),
    (
        "--grp-font-color-inverted",
        "--grp-form-button-background-color",
        _("Primary button label"),
        3.0,
    ),
    (
        "--grp-font-color",
        "--grp-table-row-background-color",
        _("Table rows"),
        4.5,
    ),
    (
        "--grp-font-color",
        "--grp-messagelist-success-background-color",
        _("Success message"),
        4.5,
    ),
    (
        "--grp-font-color",
        "--grp-messagelist-error-background-color",
        _("Error message"),
        4.5,
    ),
]

_VAR_RE = re.compile(r"^var\((--[a-z0-9_-]+)\)$")


def resolve(values: dict[str, str], name: str, depth: int = 0) -> str | None:
    if "|" in name:
        for alternative in name.split("|"):
            if alternative in values and values[alternative] != "initial":
                return resolve(values, alternative, depth)
        return None
    value = values.get(name)
    if value is None or depth > 5:
        return None
    m = _VAR_RE.match(value.strip())
    if m:
        return resolve(values, m.group(1), depth + 1)
    return value


def full_values(changes: dict[str, str], mode: str) -> dict[str, str]:
    values = {name: t.default(mode) for name, t in color_tokens().items()}
    values.update(changes)
    return values


def warnings(changes_by_mode: dict[str, dict[str, str]], modes=MODES) -> list[dict]:
    out = []
    for mode in modes:
        values = full_values(changes_by_mode.get(mode, {}), mode)
        for fg_name, bg_name, label, minimum in PAIRS:
            fg, bg = resolve(values, fg_name), resolve(values, bg_name)
            try:
                ratio = colors.contrast_ratio(colors.parse(fg), colors.parse(bg))
            except (colors.ColorError, AttributeError):
                continue  # unparsable (e.g. a CSS colour name we don't know)
            if ratio < minimum:
                out.append(
                    {
                        "mode": mode,
                        "label": str(label),
                        "ratio": round(ratio, 2),
                        "minimum": minimum,
                        "foreground": fg_name.split("|")[-1],
                        "background": bg_name.split("|")[-1],
                    }
                )
    return out
