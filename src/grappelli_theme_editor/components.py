"""Registry of styleable Grappelli components (shape, shadows, spacing, bars).

Colours live in ``--grp-*`` tokens (see ``tokens.py``); everything Grappelli
hardcodes — corner radii of individual widgets, heights, paddings, shadows,
gradients vs. flat fills, the fixed header — is described here as data:

* a :class:`Component` (top bar, buttons, filters, …) has a list of props;
* a prop knows how to validate its value and which CSS it produces.

``Theme.components`` stores ``{component: {prop: value}}``; only props the
user changed are stored, so an empty dict means "stock Grappelli".

Component rules are emitted with ``!important``: they are explicit user
choices and several of the Grappelli rules they replace are ``!important``
themselves (e.g. button radii).
"""

from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from urllib.parse import quote

from django.core.exceptions import ValidationError
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from .tokens import DARK, LIGHT, MODES, all_tokens
from .validators import validate_css_color

Rule = tuple[str, str]  # (selector, "prop:value;prop2:value2") with {v}


# Shared choice sets -------------------------------------------------------

# "grappelli" (the default, never stored) keeps whatever Grappelli does, which
# is not always "no shadow" (e.g. the glow around submit-row buttons).
SHADOWS = {
    "grappelli": (_("As in Grappelli"), ""),
    "none": (_("None"), "none"),
    "subtle": (_("Subtle"), "0 1px 2px rgba(0,0,0,.10)"),
    "soft": (_("Soft"), "0 2px 6px rgba(0,0,0,.14)"),
    "medium": (_("Medium"), "0 4px 14px rgba(0,0,0,.18)"),
    "strong": (_("Strong"), "0 10px 30px rgba(0,0,0,.28)"),
    "floating": (_("Floating"), "0 18px 50px rgba(0,0,0,.35)"),
    "hard": (_("Hard offset (brutalist)"), "4px 4px 0 rgba(0,0,0,.9)"),
}
SHADOWS_UP = {
    "grappelli": (_("As in Grappelli"), ""),
    "none": (_("None"), "none"),
    "subtle": (_("Subtle"), "0 -1px 2px rgba(0,0,0,.10)"),
    "soft": (_("Soft"), "0 -2px 8px rgba(0,0,0,.16)"),
    "strong": (_("Strong"), "0 -6px 20px rgba(0,0,0,.28)"),
    "floating": (
        _("Floating, all around (for the dock)"),
        "0 14px 40px rgba(0,0,0,.30), 0 3px 10px rgba(0,0,0,.16)",
    ),
}
TRANSFORMS = {
    "none": (_("Normal"), "text-transform:none;letter-spacing:normal"),
    "uppercase": (_("UPPERCASE"), "text-transform:uppercase;letter-spacing:.05em"),
    "small-caps": (
        _("Small caps"),
        "text-transform:none;font-variant:small-caps;letter-spacing:.03em",
    ),
}
WEIGHTS = {
    "normal": (_("Normal"), "font-weight:normal"),
    "600": (_("Semi-bold"), "font-weight:600"),
    "bold": (_("Bold"), "font-weight:bold"),
}


# Prop types ---------------------------------------------------------------


@dataclass(frozen=True)
class Prop:
    key: str
    label: str

    type = "abstract"

    def clean(self, value):  # pragma: no cover - interface
        raise NotImplementedError

    def rules(self, value, var_name: str) -> list[Rule]:
        return []

    def variables(self, value, var_name: str, mode: str) -> dict[str, str]:
        return {}

    def flatten_tokens(self, value) -> list[str]:
        return []

    def affects_header(self) -> bool:
        return False

    def as_json(self) -> dict:
        return {"key": self.key, "label": str(self.label), "type": self.type}


@dataclass(frozen=True)
class Length(Prop):
    """A px length; ``default`` is Grappelli's own value (shown in the UI)."""

    targets: tuple[Rule, ...] = ()
    default: int = 0
    min: int = 0
    max: int = 40
    header: bool = False

    type = "length"

    def clean(self, value):
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise ValidationError(gettext("Enter a whole number.")) from None
        if not self.min <= number <= self.max:
            raise ValidationError(
                gettext("Enter a value between %(min)s and %(max)s.")
                % {"min": self.min, "max": self.max}
            )
        return number

    def rules(self, value, var_name):
        return [(sel, decl.replace("{v}", f"{value}px")) for sel, decl in self.targets]

    def affects_header(self):
        return self.header

    def as_json(self):
        return {
            **super().as_json(),
            "default": self.default,
            "min": self.min,
            "max": self.max,
        }


@dataclass(frozen=True)
class Choice(Prop):
    """One of named options. Each option either:

    * maps to a CSS value substituted for ``{v}`` in ``targets``, or
    * (``option_rules``) carries its own complete rules, or
    * (``flatten``) flattens gradient tokens matching the given prefixes.
    """

    options: dict = field(default_factory=dict)
    targets: tuple[Rule, ...] = ()
    option_rules: dict = field(default_factory=dict)
    flatten: dict = field(default_factory=dict)
    default: str = ""
    header_options: tuple[str, ...] = ()

    type = "choice"

    def clean(self, value):
        if not isinstance(value, str) or value not in self.options:
            raise ValidationError(gettext("Pick one of the offered options."))
        return value

    def rules(self, value, var_name):
        if value in self.option_rules:
            return list(self.option_rules[value])
        if not self.targets:
            return []
        css_value = self.options[value][1]
        return [(sel, decl.replace("{v}", css_value)) for sel, decl in self.targets]

    def flatten_tokens(self, value):
        prefixes = self.flatten.get(value)
        if not prefixes:
            return []
        return [
            name
            for name in all_tokens()
            if name.startswith(prefixes) and "gradient-from" in name
        ]

    def as_json(self):
        return {
            **super().as_json(),
            "default": self.default,
            "options": [[k, str(v[0])] for k, v in self.options.items()],
        }


@dataclass(frozen=True)
class Color(Prop):
    """A colour with separate light/dark values: ``{"light": .., "dark": ..}``.

    ``targets`` are ``(selector, property, fallback)``; the value is emitted
    as a ``--gte-*`` variable per mode, the rule reads it with Grappelli's
    original expression as fallback, so a colour set only for light mode
    leaves dark mode untouched. With ``fallback=None`` the missing mode
    reuses the other mode's colour.
    """

    targets: tuple[tuple[str, str, str | None], ...] = ()

    type = "color"

    def clean(self, value):
        if isinstance(value, str):
            value = {LIGHT: value}
        if not isinstance(value, dict) or set(value) - set(MODES) or not value:
            raise ValidationError(gettext("Expected light and/or dark colour."))
        for color in value.values():
            validate_css_color(color)
        return {m: value[m] for m in MODES if value.get(m)}

    def rules(self, value, var_name):
        out = []
        for selector, prop, fallback in self.targets:
            ref = f"var({var_name}, {fallback})" if fallback else f"var({var_name})"
            out.append((selector, f"{prop}:{ref}"))
        return out

    def variables(self, value, var_name, mode):
        color = value.get(mode)
        other = value.get(DARK if mode == LIGHT else LIGHT)
        if color is None and any(t[2] is None for t in self.targets):
            color = other  # no fallback expression: reuse the other mode
        if color is None and other is not None:
            # Set for the other mode only: make sure that value does not leak
            # through :root into this mode — "initial" is the guaranteed-invalid
            # value, so var() uses its fallback.
            return {var_name: "initial"}
        return {var_name: color} if color else {}


_GLYPH_FORBIDDEN = set("\"'\\<>{};`")
_BIDI_CONTROLS = {chr(c) for c in (*range(0x202A, 0x202F), *range(0x2066, 0x206A))}


def validate_glyph(value) -> str:
    """A short icon: one emoji or a few characters, nothing CSS can choke on."""
    if not isinstance(value, str):
        raise ValidationError(gettext("Enter an icon (an emoji or a character)."))
    value = value.strip()
    if not 1 <= len(value) <= 8:
        raise ValidationError(gettext("An icon may have 1 to 8 characters."))
    for ch in value:
        category = unicodedata.category(ch)
        if (
            ch in _GLYPH_FORBIDDEN
            or ch in _BIDI_CONTROLS
            or category in ("Cc", "Cs", "Co", "Cn", "Zl", "Zp")
        ):
            raise ValidationError(
                gettext("This icon contains a character that is not allowed.")
            )
    return value


def css_string(text: str) -> str:
    """Quoted CSS string with every character escaped (\\hex form)."""
    return '"' + "".join(f"\\{ord(ch):x} " for ch in text) + '"'


def glyph_svg(glyph: str) -> str:
    """The glyph as an SVG data URI, for elements without ::before (inputs)."""
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='18' height='18'>"
        "<text x='9' y='14' font-size='14' text-anchor='middle' fill='white' "
        "font-family='Apple Color Emoji,Segoe UI Emoji,Noto Color Emoji,sans-serif'>"
        f"{html.escape(glyph)}</text></svg>"
    )
    return 'url("data:image/svg+xml,' + quote(svg, safe="") + '")'


# Built-in outline icons (24×24, stroke only), drawn for this package.
LINE_ICONS = {
    "save": '<path d="M5 3h11l3 3v15H5z"/><path d="M8 3v5h7V3"/>'
    '<rect x="8" y="13" width="8" height="6"/>',
    "save_check": '<path d="M5 12.5l4.5 4.5L19 7"/>',
    "save_cloud": '<path d="M7 18h10a4 4 0 0 0 .6-7.96A6 6 0 0 0 6.1 11.1 '
    '3.5 3.5 0 0 0 7 18z"/>'
    '<path d="M12 16v-5M9.5 13.5L12 11l2.5 2.5"/>',
    "save_tray": '<path d="M4 14v5h16v-5"/><path d="M12 4v10M8 10l4 4 4-4"/>',
    "continue": '<path d="M4 20l1-4L16 5l3 3L8 19z"/><path d="M14 7l3 3"/>',
    "addanother": '<path d="M12 5v14M5 12h14"/>',
    "add": '<path d="M12 5v14M5 12h14"/>',
    "delete": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>'
    '<path d="M10 11v6M14 11v6"/>',
    "search": '<circle cx="11" cy="11" r="6"/><path d="M16 16l4 4"/>',
}
LINE_COLORS = {"white": "#ffffff", "dark": "#222222", "grey": "#888888"}
# "Delete" gets a red outline icon on plain (background-less) buttons.
DELETE_LINE_COLORS = {"white": "#ff6961", "dark": "#d70015"}


def line_svg(name: str, color: str) -> str:
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='18' "
        f"height='18' fill='none' stroke='{color}' stroke-width='2' "
        f"stroke-linecap='round' stroke-linejoin='round'>{LINE_ICONS[name]}</svg>"
    ).replace('"', "'")
    return 'url("data:image/svg+xml,' + quote(svg, safe="") + '")'


@dataclass(frozen=True)
class Glyph(Prop):
    """An icon (emoji/character) used by a component's ``extra_rules``."""

    default: str = ""

    type = "glyph"

    def clean(self, value):
        return validate_glyph(value)

    def as_json(self):
        return {**super().as_json(), "default": self.default}


_URL_RE = re.compile(r"^(https://|/)[^\s\"'()\\<>;{}]+$")


@dataclass(frozen=True)
class Url(Prop):
    """An image URL (https:// or a site path such as /media/…)."""

    default: str = ""

    type = "url"

    def clean(self, value):
        if not isinstance(value, str) or not _URL_RE.match(value.strip()):
            raise ValidationError(
                gettext(
                    "Enter an https:// address or a path starting with /, "
                    "without spaces, quotes or brackets."
                )
            )
        return value.strip()


@dataclass(frozen=True)
class Component:
    key: str
    label: str
    props: tuple[Prop, ...]
    description: str = ""
    # Rules that depend on several props at once:
    # f(values, component, context) -> rules; context carries e.g. image_url.
    extra_rules: Callable | None = None

    def prop(self, key: str) -> Prop | None:
        return next((p for p in self.props if p.key == key), None)

    def value(self, values: dict, key: str):
        """Stored value or the prop's default."""
        if key in values:
            return values[key]
        return getattr(self.prop(key), "default", None)


# Selectors ----------------------------------------------------------------

BTN = (
    "a.grp-button,a[role=button].button,button.grp-button,"
    "input[type=button].grp-button,input[type=submit]"
)
_FIELDS = (
    "input[type=text]",
    "input[type=password]",
    "input[type=url]",
    "input[type=email]",
    "input[type=number]",
    "select",
)
INPUT_ONE_LINE = ",".join(_FIELDS)
INPUT = INPUT_ONE_LINE + ",textarea"
INPUT_FOCUS = ",".join(f"{s}:focus" for s in (*_FIELDS, "textarea"))
# Grappelli's submit row is also a .grp-module: keep module styling off it.
MODULE = ".grp-module:not(.grp-submit-row)"
MODULE_H2 = ".grp-module h2,.grp-group>h2"
MODULE_HEADINGS = MODULE_H2 + ",.grp-module h3,.grp-module h4"
SUBMIT_ITEMS = (
    ".grp-submit-row>ul>li,.grp-submit-row>ul>div,"
    ".grp-submit-row>div>li,.grp-submit-row>div>div"
)
FOOTER_ITEMS = (
    ".grp-submit-row.grp-fixed-footer>ul>li,.grp-submit-row.grp-fixed-footer>ul>div,"
    ".grp-submit-row.grp-fixed-footer>div>li,.grp-submit-row.grp-fixed-footer>div>div"
)
NAV_LINKS = "#grp-navigation a,#grp-user-tools>li form button"
NAV_LINKS_HOVER = "#grp-navigation a:hover,#grp-user-tools>li form button:hover"
POPUPS = ".ui-datepicker,#ui-timepicker,.ui-autocomplete"
TABLE_CELLS = "table.grp-table td,table.grp-table th"
TABLE_ALT = (
    "table.grp-table tbody tr.grp-row-even td,table.grp-table tbody tr.grp-row-even th,"
    "table.grp-table tbody tr.grp-alt td,table.grp-table tbody tr.grp-alt th"
)
DARK_BAR_GRADIENT = (
    "linear-gradient(var(--grp-dark-gradient-from), var(--grp-dark-background-color))"
)
GRADIENT_FLAT = {
    "gradient": (_("Gradient (Grappelli)"), ""),
    "flat": (_("Flat colour"), ""),
}


def _flat(selector: str, color: str) -> tuple[Rule, ...]:
    return ((selector, f"background-image:none;background-color:{color}"),)


# --- Icons & labels ---------------------------------------------------------

ADD_LINK = ".grp-object-tools a.grp-add-link"
SUBMIT_BUTTONS = {
    # glyph prop -> selector (inputs, except the delete link)
    "save_glyph": (
        ".grp-submit-row input[name=_save],.grp-submit-row input[name=_saveasnew]"
    ),
    "continue_glyph": ".grp-submit-row input[name=_continue]",
    "addanother_glyph": ".grp-submit-row input[name=_addanother]",
}
DELETE_LINK = ".grp-submit-row a.grp-delete-link"
PULLDOWN_HANDLERS = (
    ".grp-pulldown-container .grp-pulldown-handler,"
    ".grp-pulldown-container .grp-pulldown-handler:hover,"
    ".grp-pulldown-container.grp-pulldown-state-open .grp-pulldown-handler,"
    ".grp-pulldown-container.grp-pulldown-state-open .grp-pulldown-handler:hover"
)

# --- Empty area of change lists (Grappelli: diagonal stripes bitmap) ------

RESULTS = ".grp-changelist-results"


def _pattern_rules(values: dict, component: Component, context: dict) -> list[Rule]:
    pattern = component.value(values, "empty_pattern")
    if pattern == "grappelli":
        return []
    ink = "var(--gte-tables-empty_color, rgba(128,128,128,.18))"
    base = "var(--grp-module-background-color)"
    size = f"{component.value(values, 'empty_size')}px"
    backgrounds = {
        "solid": base,
        "stripes_right": (
            f"repeating-linear-gradient(45deg, {ink} 0 2px, transparent 2px {size}) "
            f"{base}"
        ),
        "stripes_left": (
            f"repeating-linear-gradient(-45deg, {ink} 0 2px, transparent 2px {size}) "
            f"{base}"
        ),
        "stripes_vertical": (
            f"repeating-linear-gradient(90deg, {ink} 0 1px, transparent 1px {size}) "
            f"{base}"
        ),
        "dots": (
            f"radial-gradient({ink} 1.5px, transparent 1.6px) 0 0 / {size} {size} "
            f"{base}"
        ),
        "grid": (
            f"linear-gradient({ink} 1px, transparent 1px) 0 0 / {size} {size}, "
            f"linear-gradient(90deg, {ink} 1px, transparent 1px) 0 0 / {size} {size} "
            f"{base}"
        ),
    }
    if pattern == "image":
        url = component.value(values, "empty_image") or context.get("image_url")
        if not url:
            return []
        background = f'{base} url("{url}") repeat'
    else:
        background = backgrounds.get(pattern)
    if background is None:
        return []
    return [(RESULTS, f"background:{background}")]


# --- Page background image (uploaded with the theme) -----------------------

PAGE_IMAGE_MODES = {
    "none": (_("No image"), ""),
    "tile": (_("Tile"), "repeat 0 0 / auto"),
    "stretch": (_("Stretch to fill"), "no-repeat 50% 50% / cover"),
    "fit": (_("Fit (whole image)"), "no-repeat 50% 50% / contain"),
    "top_left": (_("Top left"), "no-repeat 0 0 / auto"),
    "top_right": (_("Top right"), "no-repeat 100% 0 / auto"),
    "bottom_left": (_("Bottom left"), "no-repeat 0 100% / auto"),
    "bottom_right": (_("Bottom right"), "no-repeat 100% 100% / auto"),
    "center": (_("Centre"), "no-repeat 50% 50% / auto"),
}


def _page_image_rules(values: dict, component: Component, context: dict) -> list:
    mode = component.value(values, "page_image")
    url = context.get("image_url")
    if mode == "none" or not url:
        return []
    placement = PAGE_IMAGE_MODES[mode][1]
    attachment = (
        "fixed" if component.value(values, "page_image_fixed") == "fixed" else "scroll"
    )
    return [
        (
            "body",
            f'background:url("{url}") {placement} {attachment},'
            " var(--grp-body-background-color)",
        )
    ]


ICON_CHOICES = {
    "grappelli": (_("Grappelli icon"), ""),
    "hidden": (_("No icon"), ""),
    "line": (_("Outline icon (built-in)"), ""),
    "custom": (_("My emoji / character (below)"), ""),
}


def _image_box(image: str, size: int = 14, gap: bool = True) -> str:
    return (
        f'content:"";display:inline-block;width:{size}px;height:{size}px;'
        f"vertical-align:-2px;{'margin-right:6px;' if gap else ''}"
        f"background:{image} 50% 50% / contain no-repeat"
    )


def _icon_rules(values: dict, component: Component, context: dict) -> list[Rule]:
    rules: list[Rule] = []
    v = lambda key: component.value(values, key)  # noqa: E731

    add = v("add_icon")
    if add in ("hidden", "custom", "line"):
        rules += [
            (
                ADD_LINK,
                "background:linear-gradient(var(--grp-object-tools-add-gradient-from),"
                " var(--grp-object-tools-add-background-color));padding-left:15px",
            ),
            (
                ADD_LINK + ":hover",
                "background:linear-gradient(var(--grp-object-tools-background-color-hover),"
                " var(--grp-form-button-background-color))",
            ),
        ]
        if add == "custom":
            rules.append(
                (
                    ADD_LINK + "::before",
                    f"content:{css_string(v('add_glyph'))};margin-right:6px",
                )
            )
        elif add == "line":
            rules.append(
                (ADD_LINK + "::before", _image_box(line_svg("add", "#ffffff"), 12))
            )

    search = v("search_icon")
    if search == "hidden":
        rules += [
            (".grp-search-button", "display:none"),
            ("input[type=text].grp-search-field", "padding-right:10px"),
        ]
    elif search == "custom":
        rules += [
            (".grp-search-button", "background-image:none"),
            (
                ".grp-search-button::before",
                f"content:{css_string(v('search_glyph'))};display:block;"
                "font-size:13px;line-height:25px;text-align:center",
            ),
        ]
    elif search == "line":
        rules.append(
            (
                ".grp-search-button",
                f"background:{line_svg('search', LINE_COLORS['grey'])} "
                "50% 50% / 16px 16px no-repeat",
            )
        )

    arrow = v("filter_arrow")
    if arrow in ("hidden", "chevron"):
        rules.append((PULLDOWN_HANDLERS, "background-image:none"))
    if arrow == "chevron":
        rules += [
            (
                ".grp-pulldown-container .grp-pulldown-handler::after",
                f"content:{css_string('▾')};float:right;margin-right:8px",
            ),
            (
                ".grp-pulldown-container.grp-pulldown-state-open "
                ".grp-pulldown-handler::after",
                f"content:{css_string('▴')}",
            ),
        ]

    style = v("submit_style")
    if style in ("icon_text", "icon_only"):
        source = v("submit_icons")

        plain = v("submit_buttons") == "plain"
        size = int(v("icon_size"))
        box = f"{size}px {size}px"

        def icon_for(name: str) -> tuple[str, bool]:
            """(css image, is_image) for one button."""
            url = values.get(f"{name}_image")
            if url:
                return f'url("{url}")', True
            if source in LINE_COLORS:
                color = LINE_COLORS[source]
                if plain and name == "delete":
                    color = DELETE_LINE_COLORS.get(source, color)
                shape = name
                if name == "save" and v("save_line") != "floppy":
                    shape = f"save_{v('save_line')}"
                return line_svg(shape, color), True
            return glyph_svg(v(f"{name}_glyph")), False

        base_bg = (
            "linear-gradient(var(--grp-form-button-gradient-from),"
            " var(--grp-form-button-background-color))"
        )
        hover_bg = (
            "linear-gradient(var(--grp-footer-form-button-gradient-from-hover),"
            " var(--grp-footer-form-button-background-color-hover))"
        )
        for glyph_key, selector in SUBMIT_BUTTONS.items():
            name = glyph_key.removesuffix("_glyph")
            icon, _is_image = icon_for(name)
            position = "50% 50%" if style == "icon_only" else "9px 50%"
            if plain:
                decl = (
                    f"background:{icon} {position} / {box} no-repeat transparent;"
                    "border:0;box-shadow:none;color:var(--grp-font-color)"
                )
            else:
                decl = (
                    f"background-image:{icon}, {base_bg};"
                    "background-repeat:no-repeat;"
                    f"background-position:{position}, 0 0;"
                    f"background-size:{box}, auto"
                )
            if style == "icon_only":
                decl += (
                    f";color:transparent;width:{size + 24}px;min-width:0;"
                    "padding-left:0;padding-right:0;text-indent:-999px"
                )
                if plain:
                    decl += f";height:{size + 16}px"
            else:
                decl += f";padding-left:{size + 16}px"
            rules.append((selector, decl))
            # Grappelli's submit row is always the fixed footer, hence the
            # footer hover colours.
            hovered = ",".join(
                f"{part.strip()}:{state}"
                for part in selector.split(",")
                for state in ("hover", "focus")
            )
            if plain:
                rules.append(
                    (
                        hovered,
                        f"background:{icon} {position} / {box} no-repeat "
                        "rgba(127,127,127,.18);border:0;box-shadow:none",
                    )
                )
            else:
                rules.append(
                    (
                        hovered,
                        f"background-image:{icon}, {hover_bg};"
                        f"background-size:{box}, auto",
                    )
                )

        delete_image, is_image = icon_for("delete")
        if is_image:
            before = _image_box(delete_image, size, gap=style != "icon_only")
        else:
            before = f"content:{css_string(v('delete_glyph'))}" + (
                f";font-size:{size}px" if style == "icon_only" else ";margin-right:6px"
            )
        # The delete button is a link: centre its icon with flexbox (an
        # inline icon sits on the text baseline and ends up too high).
        link = "display:inline-flex;align-items:center;justify-content:center"
        if style == "icon_only":
            link += (
                f";font-size:0;padding-left:12px;padding-right:12px;"
                f"min-width:{size + 24}px"
            )
            if plain:
                link += f";height:{size + 16}px"
            before = before.replace("vertical-align:-2px;", "")
        if plain:
            link += (
                ";background:transparent;border:0;box-shadow:none;"
                "color:var(--grp-font-color-error)"
            )
            rules.append(
                (
                    DELETE_LINK + ":hover," + DELETE_LINK + ":focus",
                    "background:rgba(127,127,127,.18);border:0;box-shadow:none",
                )
            )
        rules.append((DELETE_LINK, link))
        rules.append((DELETE_LINK + "::before", before))
    return rules


ICONS = Component(
    "icons",
    _("Icons & labels"),
    (
        Choice(
            "add_icon",
            _("“Add” button icon"),
            options=ICON_CHOICES,
            default="grappelli",
        ),
        Glyph("add_glyph", _("My “Add” icon"), default="✚"),
        Choice(
            "search_icon",
            _("Search field magnifier"),
            options=ICON_CHOICES,
            default="grappelli",
        ),
        Glyph("search_glyph", _("My search icon"), default="🔍"),
        Choice(
            "filter_arrow",
            _("Filter box arrow"),
            options={
                "grappelli": (_("Grappelli arrow"), ""),
                "chevron": (_("Text chevron ▾"), ""),
                "hidden": (_("No arrow"), ""),
            },
            default="grappelli",
        ),
        Choice(
            "submit_style",
            _("Save / delete buttons"),
            options={
                "text": (_("Text only (Grappelli)"), ""),
                "icon_text": (_("Icon and text"), ""),
                "icon_only": (_("Icon only"), ""),
            },
            default="text",
        ),
        Choice(
            "submit_icons",
            _("Icons on the save / delete buttons"),
            options={
                "emoji": (_("Emoji / characters (below)"), ""),
                "white": (_("Outline icons, white"), ""),
                "dark": (_("Outline icons, dark"), ""),
            },
            default="emoji",
        ),
        Choice(
            "save_line",
            _("Outline “Save” icon"),
            options={
                "check": (_("Check mark ✓"), ""),
                "cloud": (_("Cloud with arrow up"), ""),
                "tray": (_("Arrow into a tray"), ""),
                "floppy": (_("Floppy disk (retro)"), ""),
            },
            default="check",
        ),
        Length("icon_size", _("Icon size"), default=16, min=12, max=40),
        Choice(
            "submit_buttons",
            _("Save / delete button background"),
            options={
                "filled": (_("Filled (Grappelli)"), ""),
                "plain": (_("None — just the icon, like a dock"), ""),
            },
            default="filled",
        ),
        Glyph("save_glyph", _("“Save” icon"), default="✅"),
        Glyph("continue_glyph", _("“Save and continue editing” icon"), default="📝"),
        Glyph("addanother_glyph", _("“Save and add another” icon"), default="➕"),
        Glyph("delete_glyph", _("“Delete” icon"), default="🗑️"),
        Url("save_image", _("“Save” image URL (optional)")),
        Url("continue_image", _("“Save and continue” image URL (optional)")),
        Url("addanother_image", _("“Save and add another” image URL (optional)")),
        Url("delete_image", _("“Delete” image URL (optional)")),
    ),
    _(
        "Swap or hide Grappelli's icons and put icons on the save/delete "
        "buttons: emoji, built-in outline icons or your own images "
        "(an image URL wins over the emoji)."
    ),
    extra_rules=_icon_rules,
)


COMPONENTS: tuple[Component, ...] = (
    Component(
        "general",
        _("General"),
        (
            Choice(
                "surfaces",
                _("Surfaces"),
                options={
                    "gradient": (_("Gradients (Grappelli)"), ""),
                    "flat": (_("Flat everywhere"), ""),
                },
                flatten={"flat": ("--grp-",)},
                default="gradient",
            ),
            Length(
                "content_padding",
                _("Page side margin"),
                targets=(("#grp-content", "padding-left:{v};padding-right:{v}"),),
                default=20,
                max=120,
            ),
            Choice(
                "link_decoration",
                _("Links in content"),
                options={
                    "none": (_("No underline (Grappelli)"), ""),
                    "hover": (_("Underline on hover"), ""),
                    "always": (_("Always underlined"), ""),
                },
                option_rules={
                    "hover": (
                        (
                            "#grp-content a:not(.grp-button):hover",
                            "text-decoration:underline",
                        ),
                    ),
                    "always": (
                        (
                            "#grp-content-container "
                            "a:not(.grp-button):not([class*=grp-])",
                            "text-decoration:underline",
                        ),
                    ),
                },
                default="none",
            ),
            Choice(
                "page_image",
                _("Background image (upload it above)"),
                options=PAGE_IMAGE_MODES,
                default="none",
            ),
            Choice(
                "page_image_fixed",
                _("Background image when scrolling"),
                options={
                    "scroll": (_("Scrolls with the page"), ""),
                    "fixed": (_("Stays in place"), ""),
                },
                default="scroll",
            ),
        ),
        _("Global switches that touch the whole admin."),
    ),
    Component(
        "navbar",
        _("Top bar"),
        (
            Color(
                "background",
                _("Background"),
                targets=(("#grp-navigation", "background", DARK_BAR_GRADIENT),),
            ),
            Choice(
                "surface",
                _("Fill"),
                options=GRADIENT_FLAT,
                option_rules={
                    "flat": _flat("#grp-navigation", "var(--grp-dark-background-color)")
                },
                default="gradient",
            ),
            Color(
                "text",
                _("Title colour"),
                targets=(
                    (
                        "#grp-navigation,#grp-navigation h1#grp-admin-title",
                        "color",
                        "var(--grp-font-color-inverted)",
                    ),
                ),
            ),
            Color(
                "link",
                _("Link colour"),
                targets=((NAV_LINKS, "color", "var(--grp-link-color-bright)"),),
            ),
            Color(
                "link_hover",
                _("Link hover colour"),
                targets=((NAV_LINKS_HOVER, "color", "var(--grp-font-color-inverted)"),),
            ),
            Length(
                "padding_y",
                _("Height (vertical padding)"),
                targets=(
                    ("h1#grp-admin-title", "padding-top:{v};padding-bottom:{v}"),
                    (
                        "#grp-user-tools>li a,#grp-user-tools>li button",
                        "padding-top:{v};padding-bottom:{v}",
                    ),
                ),
                default=10,
                min=2,
                max=40,
                header=True,
            ),
            Length(
                "padding_x",
                _("Side padding"),
                targets=(("#grp-navigation", "padding-left:{v};padding-right:{v}"),),
                default=20,
                max=80,
            ),
            Length(
                "title_size",
                _("Title size"),
                targets=(("h1#grp-admin-title", "font-size:{v};line-height:1.35"),),
                default=12,
                min=9,
                max=32,
                header=True,
            ),
            Choice(
                "transform",
                _("Lettering"),
                options=TRANSFORMS,
                targets=(("#grp-navigation", "{v}"),),
                default="none",
            ),
            Length(
                "border",
                _("Bottom border"),
                targets=(
                    (
                        "#grp-navigation",
                        "border-bottom:{v} solid "
                        "var(--gte-navbar-border_color, var(--grp-link-color))",
                    ),
                ),
                default=0,
                max=8,
                header=True,
            ),
            Color("border_color", _("Bottom border colour")),
            Choice(
                "shadow",
                _("Shadow"),
                options=SHADOWS,
                targets=(("header#grp-header", "box-shadow:{v}"),),
                default="grappelli",
            ),
            Length(
                "dropdown_radius",
                _("Drop-down menu rounding"),
                targets=(
                    (
                        "#grp-navigation ul li.grp-collapse.grp-open>ul",
                        "border-radius:0 0 {v} {v}",
                    ),
                ),
                default=3,
                max=20,
            ),
            Choice(
                "dropdown_shadow",
                _("Drop-down menu shadow"),
                options=SHADOWS,
                targets=(
                    (
                        "#grp-navigation ul li.grp-collapse.grp-open>ul",
                        "box-shadow:{v}",
                    ),
                ),
                default="grappelli",
            ),
            Choice(
                "position",
                _("Behaviour when scrolling"),
                options={
                    "fixed": (_("Always visible (Grappelli)"), ""),
                    "static": (_("Scrolls away with the page"), ""),
                },
                default="fixed",
                header_options=("static",),
            ),
        ),
        _("Grappelli's dark bar at the top: site title and user menu."),
    ),
    Component(
        "breadcrumbs",
        _("Breadcrumbs bar"),
        (
            Color(
                "background",
                _("Background"),
                targets=(
                    (
                        "#grp-context-navigation",
                        "background",
                        "var(--grp-context-navigation-background-color)",
                    ),
                ),
            ),
            Color(
                "link",
                _("Link colour"),
                targets=(("#grp-breadcrumbs>ul a", "color", "var(--grp-link-color)"),),
            ),
            Color(
                "text",
                _("Current page colour"),
                targets=(("#grp-breadcrumbs>ul", "color", "var(--grp-font-color)"),),
            ),
            Color(
                "border",
                _("Bottom border colour"),
                targets=(
                    (
                        "#grp-context-navigation",
                        "border-bottom-color",
                        "var(--grp-context-navigation-border-color)",
                    ),
                ),
            ),
            Length(
                "padding_y",
                _("Height (vertical padding)"),
                targets=(
                    ("#grp-breadcrumbs>ul", "padding-top:{v};padding-bottom:{v}"),
                ),
                default=5,
                max=24,
                header=True,
            ),
            Choice(
                "text_shadow",
                _("Text shadow"),
                options={
                    "keep": (_("Embossed (Grappelli)"), ""),
                    "none": (_("None"), ""),
                },
                option_rules={"none": (("#grp-breadcrumbs>ul", "text-shadow:none"),)},
                default="keep",
            ),
            Choice(
                "visibility",
                _("Visibility"),
                options={"visible": (_("Visible"), ""), "hidden": (_("Hidden"), "")},
                option_rules={"hidden": (("#grp-context-navigation", "display:none"),)},
                default="visible",
                header_options=("hidden",),
            ),
        ),
    ),
    Component(
        "buttons",
        _("Buttons"),
        (
            Length(
                "radius",
                _("Rounding"),
                targets=((BTN, "border-radius:{v}"),),
                default=5,
                max=30,
            ),
            Length(
                "height",
                _("Height"),
                targets=(
                    (
                        BTN,
                        "height:{v};line-height:calc({v} - 2px);"
                        "padding-top:0;padding-bottom:0",
                    ),
                ),
                default=28,
                min=18,
                max=56,
            ),
            Length(
                "padding_x",
                _("Side padding"),
                targets=((BTN, "padding-left:{v};padding-right:{v}"),),
                default=10,
                min=2,
                max=48,
            ),
            Length(
                "border",
                _("Border width"),
                targets=((BTN, "border-width:{v}"),),
                default=1,
                max=4,
            ),
            Color(
                "border_color",
                _("Border colour"),
                targets=(
                    (BTN, "border-color", None),
                    (
                        ".grp-fixed-footer a.grp-button:hover,"
                        ".grp-fixed-footer input[type=submit]:hover,"
                        ".grp-fixed-footer button.grp-button:hover",
                        "border-color",
                        None,
                    ),
                ),
            ),
            Choice(
                "surface",
                _("Fill"),
                options=GRADIENT_FLAT,
                flatten={"flat": ("--grp-form-button-", "--grp-footer-form-button-")},
                default="gradient",
            ),
            Choice(
                "shadow",
                _("Shadow"),
                options=SHADOWS,
                targets=((BTN, "box-shadow:{v}"),),
                default="grappelli",
            ),
            Choice(
                "weight",
                _("Font weight"),
                options=WEIGHTS,
                targets=((BTN, "{v}"),),
                default="bold",
            ),
            Choice(
                "transform",
                _("Lettering"),
                options=TRANSFORMS,
                targets=((BTN, "{v}"),),
                default="none",
            ),
            Choice(
                "dim_secondary",
                _("Secondary buttons in the submit row"),
                options={
                    "dimmed": (_("Dimmed until hover (Grappelli)"), ""),
                    "full": (_("Fully opaque"), ""),
                },
                option_rules={
                    "full": (
                        (
                            ".grp-submit-row input.grp-button,"
                            ".grp-submit-row a.grp-button,"
                            ".grp-submit-row button.grp-button",
                            "opacity:1",
                        ),
                    )
                },
                default="dimmed",
            ),
        ),
    ),
    Component(
        "inputs",
        _("Form fields"),
        (
            Length(
                "radius",
                _("Rounding"),
                targets=((INPUT, "border-radius:{v}"),),
                default=3,
                max=24,
            ),
            Length(
                "height",
                _("Height"),
                targets=((INPUT_ONE_LINE, "height:{v}"),),
                default=25,
                min=18,
                max=56,
            ),
            Length(
                "padding_x",
                _("Side padding"),
                targets=((INPUT, "padding-left:{v};padding-right:{v}"),),
                default=5,
                max=24,
            ),
            Length(
                "border",
                _("Border width"),
                targets=((INPUT, "border-width:{v}"),),
                default=1,
                max=4,
            ),
            Choice(
                "inner_shadow",
                _("Inner shadow"),
                options={
                    "inset": (_("Inset (Grappelli)"), ""),
                    "none": (_("None"), ""),
                },
                option_rules={"none": ((INPUT, "box-shadow:none"),)},
                default="inset",
            ),
            Choice(
                "focus",
                _("Focus highlight"),
                options={
                    "grappelli": (_("Darker border (Grappelli)"), ""),
                    "ring": (_("Accent ring"), ""),
                },
                option_rules={
                    "ring": (
                        (
                            INPUT_FOCUS,
                            "border-color:var(--grp-link-color);box-shadow:0 0 0 3px "
                            "color-mix(in srgb, var(--grp-link-color) 30%, "
                            "transparent)",
                        ),
                    )
                },
                default="grappelli",
            ),
            Choice(
                "weight",
                _("Font weight"),
                options=WEIGHTS,
                targets=((INPUT, "{v}"),),
                default="bold",
            ),
        ),
    ),
    Component(
        "modules",
        _("Modules & fieldsets"),
        (
            Length(
                "radius",
                _("Rounding"),
                targets=(
                    (MODULE, "border-radius:{v}"),
                    (
                        MODULE_H2,
                        "border-top-left-radius:{v};border-top-right-radius:{v}",
                    ),
                ),
                default=3,
                max=24,
            ),
            Length(
                "group_radius",
                _("Inline group rounding"),
                targets=((".grp-group", "border-radius:{v}"),),
                default=5,
                max=24,
            ),
            Length(
                "border",
                _("Border width"),
                targets=((MODULE, "border-width:{v}"),),
                default=1,
                max=4,
            ),
            Choice(
                "shadow",
                _("Shadow"),
                options=SHADOWS,
                targets=(
                    (
                        MODULE + ":not(.grp-module .grp-module),.grp-group",
                        "box-shadow:{v}",
                    ),
                ),
                default="grappelli",
            ),
            Length(
                "spacing",
                _("Space between modules"),
                targets=((MODULE + ",.grp-group", "margin-bottom:{v}"),),
                default=5,
                max=40,
            ),
            Color(
                "header_background",
                _("Header background"),
                targets=(
                    (
                        MODULE_H2,
                        "background",
                        "linear-gradient(var(--grp-module-h2-gradient-from), "
                        "var(--grp-module-h2-gradient-to))",
                    ),
                ),
            ),
            Color(
                "header_text",
                _("Header text colour"),
                targets=((MODULE_HEADINGS, "color", "inherit"),),
            ),
            Choice(
                "header_surface",
                _("Header fill"),
                options=GRADIENT_FLAT,
                flatten={"flat": ("--grp-module-h",)},
                default="gradient",
            ),
            Length(
                "header_padding",
                _("Header height (vertical padding)"),
                targets=((MODULE_HEADINGS, "padding-top:{v};padding-bottom:{v}"),),
                default=5,
                max=20,
            ),
            Length(
                "header_size",
                _("Header text size"),
                targets=((MODULE_H2, "font-size:{v}"),),
                default=12,
                min=9,
                max=24,
            ),
            Choice(
                "header_transform",
                _("Header lettering"),
                options=TRANSFORMS,
                targets=((MODULE_HEADINGS, "{v}"),),
                default="none",
            ),
            Choice(
                "header_text_shadow",
                _("Header text shadow"),
                options={
                    "keep": (_("Embossed (Grappelli)"), ""),
                    "none": (_("None"), ""),
                },
                option_rules={"none": ((MODULE_HEADINGS, "text-shadow:none"),)},
                default="keep",
            ),
        ),
    ),
    Component(
        "filters",
        _("Filters & search"),
        (
            Length(
                "radius",
                _("Filter box rounding"),
                targets=(
                    (
                        ".grp-pulldown-container,"
                        ".grp-pulldown-container .grp-pulldown-handler",
                        "border-radius:{v}",
                    ),
                    (
                        ".grp-pulldown-container .grp-pulldown-content",
                        "border-bottom-left-radius:{v};border-bottom-right-radius:{v}",
                    ),
                ),
                default=4,
                max=24,
            ),
            Length(
                "border",
                _("Filter box border width"),
                targets=((".grp-filter .grp-pulldown-container", "border-width:{v}"),),
                default=1,
                max=4,
            ),
            Choice(
                "open_shadow",
                _("Shadow of the open filter box"),
                options={**SHADOWS, "grappelli": (_("Large glow (Grappelli)"), "")},
                targets=(
                    (
                        ".grp-pulldown-container.grp-pulldown-state-open",
                        "box-shadow:{v}",
                    ),
                ),
                default="grappelli",
            ),
            Length(
                "search_radius",
                _("Search field rounding"),
                targets=(
                    ("input[type=text].grp-search-field", "border-radius:{v}"),
                    ("form#grp-changelist-search-form", "border-radius:{v}"),
                ),
                default=20,
                max=30,
            ),
        ),
        _("The change list's filter drop-down/sidebar and the search box."),
    ),
    Component(
        "tables",
        _("Tables & change lists"),
        (
            Length(
                "radius",
                _("Rounding"),
                targets=(("table.grp-table", "border-radius:{v}"),),
                default=3,
                max=20,
            ),
            Length(
                "cell_padding_y",
                _("Row height (vertical padding)"),
                targets=((TABLE_CELLS, "padding-top:{v};padding-bottom:{v}"),),
                default=10,
                min=2,
                max=24,
            ),
            Length(
                "cell_padding_x",
                _("Cell side padding"),
                targets=((TABLE_CELLS, "padding-left:{v};padding-right:{v}"),),
                default=10,
                min=2,
                max=32,
            ),
            Length(
                "header_padding_y",
                _("Header height (vertical padding)"),
                targets=(
                    ("table.grp-table thead th", "padding-top:{v};padding-bottom:{v}"),
                ),
                default=6,
                min=2,
                max=20,
            ),
            Choice(
                "header_surface",
                _("Header fill"),
                options=GRADIENT_FLAT,
                option_rules={
                    "flat": _flat(
                        "table.grp-table thead th", "var(--grp-table-background-color)"
                    )
                },
                default="gradient",
            ),
            Choice(
                "header_transform",
                _("Header lettering"),
                options=TRANSFORMS,
                targets=(("table.grp-table thead th", "{v}"),),
                default="none",
            ),
            Choice(
                "stripes",
                _("Zebra stripes"),
                options={"on": (_("On (Grappelli)"), ""), "off": (_("Off"), "")},
                option_rules={
                    "off": (
                        (TABLE_ALT, "background:var(--grp-table-row-background-color)"),
                    )
                },
                default="on",
            ),
            Choice(
                "grid",
                _("Cell borders"),
                options={
                    "grid": (_("Grid (Grappelli)"), ""),
                    "rows": (_("Horizontal lines only"), ""),
                },
                option_rules={
                    "rows": (
                        (
                            "table.grp-table tbody tr td,table.grp-table tbody tr th,"
                            "table.grp-table thead th",
                            "border-left:0",
                        ),
                    )
                },
                default="grid",
            ),
            Color(
                "row_hover",
                _("Row hover colour"),
                targets=(
                    (
                        "table.grp-table tbody tr:hover td,"
                        "table.grp-table tbody tr:hover th",
                        "background",
                        None,
                    ),
                ),
            ),
            Choice(
                "empty_pattern",
                _("Empty area next to the table"),
                options={
                    "grappelli": (_("Diagonal stripes (Grappelli)"), ""),
                    "solid": (_("Plain"), ""),
                    "stripes_right": (_("Stripes ╱"), ""),
                    "stripes_left": (_("Stripes ╲"), ""),
                    "stripes_vertical": (_("Vertical lines"), ""),
                    "dots": (_("Dots"), ""),
                    "grid": (_("Grid"), ""),
                    "image": (_("My image (below)"), ""),
                },
                default="grappelli",
            ),
            Color("empty_color", _("Pattern colour")),
            Length("empty_size", _("Pattern spacing"), default=12, min=4, max=60),
            Url("empty_image", _("Pattern image URL")),
        ),
    ),
    Component(
        "messages",
        _("Messages"),
        (
            Length(
                "radius",
                _("Rounding"),
                targets=((".grp-messagelist>li", "border-radius:{v}"),),
                default=3,
                max=24,
            ),
            Length(
                "padding_y",
                _("Vertical padding"),
                targets=(
                    (".grp-messagelist>li", "padding-top:{v};padding-bottom:{v}"),
                ),
                default=5,
                max=24,
            ),
            Choice(
                "style",
                _("Style"),
                options={
                    "box": (_("Bordered box (Grappelli)"), ""),
                    "accent": (_("Thick left edge"), ""),
                },
                option_rules={
                    "accent": ((".grp-messagelist>li", "border-width:0 0 0 5px"),)
                },
                default="box",
            ),
            Choice(
                "shadow",
                _("Shadow"),
                options=SHADOWS,
                targets=((".grp-messagelist>li", "box-shadow:{v}"),),
                default="grappelli",
            ),
            Choice(
                "weight",
                _("Font weight"),
                options=WEIGHTS,
                targets=((".grp-messagelist>li", "{v}"),),
                default="bold",
            ),
        ),
    ),
    Component(
        "object_tools",
        _("Object tools (Add, History…)"),
        (
            Length(
                "radius",
                _("Rounding"),
                targets=((".grp-object-tools a", "border-radius:{v}"),),
                default=30,
                max=30,
            ),
            Length(
                "padding_x",
                _("Side padding"),
                targets=(
                    (".grp-object-tools a", "padding-left:{v};padding-right:{v}"),
                ),
                default=15,
                max=40,
            ),
            Choice(
                "opacity",
                _("Resting state"),
                options={
                    "dimmed": (_("Half-transparent (Grappelli)"), ""),
                    "full": (_("Fully opaque"), ""),
                },
                option_rules={"full": ((".grp-object-tools a", "opacity:1"),)},
                default="dimmed",
            ),
            Choice(
                "surface",
                _("Fill"),
                options=GRADIENT_FLAT,
                flatten={"flat": ("--grp-object-tools-",)},
                default="gradient",
            ),
            Choice(
                "shadow",
                _("Shadow"),
                options=SHADOWS,
                targets=((".grp-object-tools a", "box-shadow:{v}"),),
                default="grappelli",
            ),
            Choice(
                "transform",
                _("Lettering"),
                options=TRANSFORMS,
                targets=((".grp-object-tools a", "{v}"),),
                default="none",
            ),
        ),
    ),
    Component(
        "footer",
        _("Bottom submit bar"),
        (
            Choice(
                "position",
                _("Position"),
                options={
                    "grappelli": (_("Fixed at the bottom (Grappelli)"), ""),
                    "flush": (_("Glued to the bottom edge, full width"), ""),
                    "dock": (_("Dock: centred, only as wide as the buttons"), ""),
                    "static": (_("At the end of the form (does not float)"), ""),
                },
                option_rules={
                    "flush": (
                        (
                            ".grp-fixed-footer",
                            "left:0;right:0;bottom:0;width:100%;margin:0;"
                            "border-radius:0;transform:none",
                        ),
                    ),
                    "dock": (
                        (
                            ".grp-fixed-footer",
                            "left:50%;right:auto;bottom:14px;width:auto;"
                            "max-width:calc(100% - 40px);margin:0;"
                            "transform:translateX(-50%);border-radius:16px;"
                            "padding:8px 12px 3px;"
                            "box-shadow:0 10px 30px rgba(0,0,0,.30)",
                        ),
                        (".grp-fixed-footer>ul", "display:flex;gap:0"),
                    ),
                    "static": (
                        (
                            ".grp-fixed-footer",
                            "position:relative;left:auto;bottom:auto;margin:20px 0 0;"
                            "border-radius:6px",
                        ),
                    ),
                },
                default="grappelli",
            ),
            Color(
                "background",
                _("Background"),
                targets=((".grp-fixed-footer", "background", DARK_BAR_GRADIENT),),
            ),
            Choice(
                "surface",
                _("Fill"),
                options=GRADIENT_FLAT,
                option_rules={
                    "flat": _flat(
                        ".grp-fixed-footer", "var(--grp-dark-background-color)"
                    )
                },
                default="gradient",
            ),
            Choice(
                "shadow",
                _("Shadow"),
                options=SHADOWS_UP,
                targets=((".grp-fixed-footer", "box-shadow:{v}"),),
                default="grappelli",
            ),
            Length(
                "dock_offset",
                _("Distance from the bottom (dock)"),
                targets=((".grp-fixed-footer", "bottom:{v}"),),
                default=14,
                max=80,
            ),
            Length(
                "item_radius",
                _("Button frame rounding"),
                targets=((SUBMIT_ITEMS, "border-radius:{v}"),),
                default=7,
                max=24,
            ),
            Color(
                "item_background",
                _("Button frame colour"),
                targets=(
                    (
                        FOOTER_ITEMS,
                        "background",
                        "var(--grp-fixed-footer-item-background-color)",
                    ),
                ),
            ),
            Choice(
                "item_frame",
                _("Button frames"),
                options={"on": (_("Shown (Grappelli)"), ""), "off": (_("Hidden"), "")},
                option_rules={
                    "off": ((FOOTER_ITEMS, "background:transparent;padding:0"),)
                },
                default="on",
            ),
        ),
    ),
    Component(
        "pagination",
        _("Pagination"),
        (
            Length(
                "radius",
                _("Rounding"),
                targets=(
                    (".grp-pagination ul li", "border-radius:{v}"),
                    (
                        ".grp-pagination ul li a,.grp-pagination ul li span",
                        "border-radius:{v}",
                    ),
                ),
                default=3,
                max=20,
            ),
            Length(
                "gap",
                _("Gap"),
                targets=((".grp-pagination ul li", "margin-right:{v}"),),
                default=1,
                max=12,
            ),
        ),
    ),
    Component(
        "login",
        _("Login page"),
        (
            Color(
                "background",
                _("Page background"),
                targets=(
                    (
                        "body.grp-login",
                        "background",
                        "var(--grp-body-background-color)",
                    ),
                ),
            ),
            Length(
                "radius",
                _("Login box rounding"),
                targets=(
                    ("body.grp-login .grp-module-login", "border-radius:{v}"),
                    (
                        "body.grp-login .grp-module-login h1",
                        "border-top-left-radius:{v};border-top-right-radius:{v}",
                    ),
                ),
                default=6,
                max=30,
            ),
            Choice(
                "shadow",
                _("Login box shadow"),
                options=SHADOWS,
                targets=(("body.grp-login .grp-module-login", "box-shadow:{v}"),),
                default="grappelli",
            ),
        ),
    ),
    Component(
        "popups",
        _("Date picker & pop-ups"),
        (
            Length(
                "radius",
                _("Rounding"),
                targets=((POPUPS, "border-radius:{v}"),),
                default=3,
                max=20,
            ),
            Choice(
                "shadow",
                _("Shadow"),
                options={**SHADOWS, "grappelli": (_("Large glow (Grappelli)"), "")},
                targets=((POPUPS, "box-shadow:{v}"),),
                default="grappelli",
            ),
        ),
    ),
)

COMPONENTS = (
    *(
        replace(c, extra_rules=_pattern_rules)
        if c.key == "tables"
        else replace(c, extra_rules=_page_image_rules)
        if c.key == "general"
        else c
        for c in COMPONENTS
    ),
    ICONS,
)
COMPONENTS_BY_KEY = {c.key: c for c in COMPONENTS}

# Grappelli's header is position:fixed and the content below it has a
# hardcoded 80px top padding (≈62px of header + 18px gap). Once the header's
# height changes, the offset follows the measured height instead: the tiny
# ``header-offset.js`` (loaded by the template tag) keeps --gte-header-height
# up to date.
HEADER_MEASURED_RULES: tuple[Rule, ...] = (
    ("#grp-content", "padding-top:calc(var(--gte-header-height, 62px) + 18px)"),
)
HEADER_STATIC_RULES: tuple[Rule, ...] = (
    ("header#grp-header", "position:relative;float:none"),
    ("#grp-content", "padding-top:20px"),
)


def var_name(component: str, prop: str) -> str:
    return f"--gte-{component}-{prop}"


def validate_components(value) -> dict:
    """Validate ``Theme.components``; returns the cleaned dict.

    Values equal to Grappelli's default are dropped, so the stored JSON only
    lists real changes.
    """
    if not isinstance(value, dict):
        raise ValidationError(gettext("Component styles must be a JSON object."))
    cleaned: dict = {}
    errors = []
    for comp_key, props in value.items():
        component = COMPONENTS_BY_KEY.get(comp_key)
        if component is None or not isinstance(props, dict):
            errors.append(gettext("Unknown component %(key)s.") % {"key": comp_key})
            continue
        for prop_key, raw in props.items():
            prop = component.prop(prop_key)
            if prop is None:
                errors.append(
                    gettext("Unknown property %(c)s.%(p)s.")
                    % {"c": comp_key, "p": prop_key}
                )
                continue
            if raw in (None, "", {}):
                continue
            try:
                clean = prop.clean(raw)
            except ValidationError as e:
                errors.append(f"{component.label} / {prop.label}: {e.messages[0]}")
                continue
            if clean == getattr(prop, "default", object()):
                continue
            cleaned.setdefault(comp_key, {})[prop_key] = clean
    if errors:
        raise ValidationError(errors)
    return cleaned


def _iter_values(components: dict):
    for comp_key, props in (components or {}).items():
        component = COMPONENTS_BY_KEY.get(comp_key)
        if component is None:
            continue
        for prop_key, value in props.items():
            prop = component.prop(prop_key)
            if prop is not None:
                yield comp_key, prop, value


def component_rules(components: dict, context: dict | None = None) -> list[Rule]:
    rules: list[Rule] = []
    resized = static = False
    for comp_key, prop, value in _iter_values(components):
        rules.extend(prop.rules(value, var_name(comp_key, prop.key)))
        if prop.affects_header():
            resized = True
        if isinstance(prop, Choice) and value in prop.header_options:
            if prop.key == "position":
                static = True
            else:
                resized = True
    for comp_key, values in (components or {}).items():
        component = COMPONENTS_BY_KEY.get(comp_key)
        if component is not None and component.extra_rules and values:
            rules.extend(component.extra_rules(values, component, context or {}))
    if static:
        rules.extend(HEADER_STATIC_RULES)
    elif resized:
        rules.extend(HEADER_MEASURED_RULES)
    return rules


def component_variables(components: dict, mode: str) -> dict[str, str]:
    out = {}
    for comp_key, prop, value in _iter_values(components):
        out.update(prop.variables(value, var_name(comp_key, prop.key), mode))
    return out


def flattened_tokens(components: dict) -> list[str]:
    names: list[str] = []
    for _comp_key, prop, value in _iter_values(components):
        names.extend(prop.flatten_tokens(value))
    return names


# What the preview inspector treats as "part of" each component: clicking an
# element highlights the components whose selector matches it or its nearest
# ancestor (see editor.js).
INSPECT_SELECTORS: dict[str, str] = {
    "general": "body",
    "navbar": "#grp-navigation",
    "breadcrumbs": "#grp-context-navigation",
    "buttons": BTN + ",.grp-button",
    "inputs": INPUT,
    "modules": MODULE + ",.grp-group",
    "filters": (
        ".grp-filter,.grp-pulldown-container,#grp-changelist-search-form,"
        "#grp-filters,.grp-search-field"
    ),
    "tables": "table.grp-table,.grp-table",
    "messages": ".grp-messagelist>li",
    "object_tools": ".grp-object-tools",
    "footer": ".grp-fixed-footer,.grp-submit-row",
    "pagination": ".grp-pagination",
    "login": "body.grp-login .grp-module-login",
    "popups": POPUPS,
    "icons": (
        ".grp-object-tools a.grp-add-link,.grp-search-button,"
        ".grp-pulldown-handler,.grp-submit-row .grp-button"
    ),
}


# Sections expanded the first time someone opens the editor.
DEFAULT_OPEN = ("navbar", "buttons", "footer")


def editor_schema() -> list[dict]:
    return [
        {
            "key": c.key,
            "label": str(c.label),
            "description": str(c.description),
            "inspect": INSPECT_SELECTORS.get(c.key, ""),
            "open": c.key in DEFAULT_OPEN,
            "props": [p.as_json() for p in c.props],
        }
        for c in COMPONENTS
    ]
