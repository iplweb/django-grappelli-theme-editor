"""Registry of Grappelli's ``--grp-*`` CSS custom properties.

Raw defaults come from the generated ``tokens_data`` module; this module adds
grouping (for the editor UI) and the *palette family* of every token (which
seed colour drives it in the simple editor, see ``palette.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from django.utils.translation import gettext_lazy as _

from . import colors, tokens_data

LIGHT = "light"
DARK = "dark"
MODES = (LIGHT, DARK)

# (prefix, group) — first match wins, so longer prefixes go first.
_GROUP_PREFIXES: list[tuple[str, str]] = [
    ("--grp-bg-", "images"),
    ("--grp-spritesheet", "images"),
    ("--grp-footer-form-button-", "buttons"),
    ("--grp-form-button-", "buttons"),
    ("--grp-button-", "buttons"),
    ("--grp-submit-", "buttons"),
    ("--grp-object-tools-", "chrome"),
    ("--grp-dark-", "chrome"),
    ("--grp-context-navigation-", "chrome"),
    ("--grp-nav-", "chrome"),
    ("--grp-fixed-footer-", "chrome"),
    ("--grp-pulldown-", "chrome"),
    ("--grp-login-", "chrome"),
    ("--grp-link-", "links"),
    ("--grp-form-", "forms"),
    ("--grp-error", "forms"),
    ("--grp-selector-", "forms"),
    ("--grp-select2-", "forms"),
    ("--grp-module-", "modules"),
    ("--grp-group-", "modules"),
    ("--grp-row-", "modules"),
    ("--grp-predelete-", "modules"),
    ("--grp-delete-", "modules"),
    ("--grp-table-", "tables"),
    ("--grp-tabular-", "tables"),
    ("--grp-changelist-", "tables"),
    ("--grp-pagination-", "tables"),
    ("--grp-sortable-", "tables"),
    ("--grp-messagelist-", "messages"),
    ("--grp-datepicker-", "widgets"),
    ("--grp-timepicker-", "widgets"),
    ("--grp-ui-", "widgets"),
    ("--grp-doc-", "docs"),
]

GROUPS: list[tuple[str, str]] = [
    ("base", _("Base")),
    ("links", _("Links")),
    ("chrome", _("Header, navigation & footer")),
    ("buttons", _("Buttons")),
    ("forms", _("Form fields")),
    ("modules", _("Modules & fieldsets")),
    ("tables", _("Tables & change lists")),
    ("messages", _("Messages")),
    ("widgets", _("Date/time pickers & widgets")),
    ("docs", _("Documentation pages")),
]

# Tokens whose colour has a meaning of its own (highlighting, docs) and
# should never be dragged along by a seed colour.
_KEEP = {
    "--grp-mark-background-color",
    "--grp-mark-font-color",
    "--grp-sortable-helper-background-color",
    "--grp-table-row-selected-background-color",
    "--grp-doc-color",
    "--grp-doc-rule-color",
    "--grp-doc-code-background-color",
    "--grp-doc-code-border-color",
}

# Prefixes of tokens that belong to the dark header/footer "chrome".
_CHROME_PREFIXES = (
    "--grp-dark-",
    "--grp-fixed-footer-",
    "--grp-object-tools-",
    "--grp-nav-dropdown-",
)

# Families used by palette.py. "keep" = never recoloured.
FAMILY_KEEP = "keep"
FAMILY_NEUTRAL = "neutral"
FAMILY_CHROME = "chrome"


@dataclass(frozen=True)
class Token:
    name: str
    group: str
    kind: str  # "color" | "image"
    light: str
    dark: str
    family_light: str
    family_dark: str

    @property
    def label(self) -> str:
        return self.name.removeprefix("--grp-").replace("-", " ").capitalize()

    def default(self, mode: str) -> str:
        return self.light if mode == LIGHT else self.dark

    def family(self, mode: str) -> str:
        return self.family_light if mode == LIGHT else self.family_dark


def _group_for(name: str) -> str:
    for prefix, group in _GROUP_PREFIXES:
        if name.startswith(prefix):
            return group
    return "base"


def _family_for(name: str, value: str) -> str:
    if name in _KEEP:
        return FAMILY_KEEP
    try:
        c = colors.parse(value)
    except colors.ColorError:
        return FAMILY_KEEP
    h, s, l_ = colors.to_hsl(c)
    if s < 0.15 or l_ < 0.04 or l_ > 0.97:
        if name.startswith(_CHROME_PREFIXES):
            return FAMILY_CHROME
        return FAMILY_NEUTRAL
    if 170 <= h <= 235:
        return "accent"
    if h <= 20 or h >= 330:
        return "danger"
    if 70 <= h <= 160:
        return "success"
    if 35 <= h < 70:
        return "warning"
    return FAMILY_KEEP


@cache
def all_tokens() -> dict[str, Token]:
    out: dict[str, Token] = {}
    for name, light in tokens_data.LIGHT_DEFAULTS.items():
        dark = tokens_data.DARK_DEFAULTS[name]
        kind = "image" if "url(" in light else "color"
        out[name] = Token(
            name=name,
            group=_group_for(name),
            kind=kind,
            light=light,
            dark=dark,
            family_light=_family_for(name, light) if kind == "color" else "keep",
            family_dark=_family_for(name, dark) if kind == "color" else "keep",
        )
    return out


def color_tokens() -> dict[str, Token]:
    return {k: t for k, t in all_tokens().items() if t.kind == "color"}


def grouped_color_tokens() -> list[tuple[str, str, list[Token]]]:
    """[(group key, label, [tokens])] in display order."""
    toks = color_tokens().values()
    return [
        (key, label, sorted((t for t in toks if t.group == key), key=lambda t: t.name))
        for key, label in GROUPS
    ]
