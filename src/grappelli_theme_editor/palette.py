"""Simple-mode palette: derive all ``--grp-*`` colours from a few seed colours.

Instead of hand-writing ~200 formulas, every token is *re-mapped relative to
Grappelli's own default*: each token belongs to a family (see
``tokens._family_for``) whose reference colour is a well-known Grappelli
token (e.g. the accent family is anchored at ``--grp-link-color``). When the
user changes a seed, every token of the family moves the same way the
reference moved — hue rotates by the same angle, saturation scales by the
same factor and lightness is re-mapped piecewise-linearly so that the
reference lands exactly on the seed while black and white stay put.

Neutral greys are re-mapped between the new page background and text colour
(and towards black/white outside that range), which also tints them when the
chosen background/text are not pure greys.

The live preview in the editor posts the form to the server, which renders
the CSS with this very code — there is no JavaScript port to keep in sync.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _

from . import colors
from .tokens import DARK, FAMILY_CHROME, FAMILY_NEUTRAL, LIGHT, color_tokens


@dataclass(frozen=True)
class Seed:
    key: str
    label: str
    source: str  # token whose Grappelli default is the reference colour
    derive_dark: bool  # derive dark seed from the light one when unset


SEEDS: list[Seed] = [
    Seed("accent", _("Accent (links, primary buttons)"), "--grp-link-color", True),
    Seed("background", _("Page background"), "--grp-body-background-color", False),
    Seed("text", _("Text"), "--grp-font-color", False),
    Seed("chrome", _("Header & footer bar"), "--grp-dark-background-color", False),
    Seed("danger", _("Errors & delete"), "--grp-font-color-error", True),
    Seed(
        "success",
        _("Success messages"),
        "--grp-messagelist-success-background-color",
        True,
    ),
    Seed(
        "warning",
        _("Warning messages"),
        "--grp-messagelist-warning-background-color",
        True,
    ),
]
SEED_KEYS = [s.key for s in SEEDS]


def seed_defaults(mode: str) -> dict[str, str]:
    toks = color_tokens()
    return {
        s.key: colors.to_hex(colors.parse(toks[s.source].default(mode))) for s in SEEDS
    }


# Seeds used as text colours: when derived for dark mode they are lightened
# until they read well on the dark page background.
_TEXT_SEEDS = {"accent", "danger"}


def _readable_on(
    color: colors.RGBA, background: colors.RGBA, minimum: float = 4.5
) -> colors.RGBA:
    h, s, l_ = colors.to_hsl(color)
    lighter = colors.relative_luminance(background) < 0.2
    step = 0.02 if lighter else -0.02
    while colors.contrast_ratio(color, background) < minimum and 0 < l_ < 1:
        l_ += step
        color = colors.from_hsl(h, s, l_, color[3])
    return color


def effective_seeds(seeds: dict, mode: str) -> dict[str, str]:
    """Seeds actually used for ``mode`` (only those that differ from default).

    ``seeds`` is the ``Theme.seeds`` JSON: ``{"light": {...}, "dark": {...}}``.
    For dark mode, an unset accent/danger/success/warning seed is derived
    from the light one: same hue and saturation, Grappelli's dark lightness.
    """
    defaults = seed_defaults(mode)
    chosen = dict((seeds or {}).get(mode) or {})
    if mode == DARK:
        light_chosen = (seeds or {}).get(LIGHT) or {}
        for s in SEEDS:
            if s.derive_dark and s.key not in chosen and s.key in light_chosen:
                h, sat, _l = colors.to_hsl(colors.parse(light_chosen[s.key]))
                _h, _s, dark_l = colors.to_hsl(colors.parse(defaults[s.key]))
                derived = colors.from_hsl(h, sat, dark_l)
                if s.key in _TEXT_SEEDS:
                    background = chosen.get("background", defaults["background"])
                    derived = _readable_on(derived, colors.parse(background))
                chosen[s.key] = colors.to_hex(derived)
    out = {}
    for key, value in chosen.items():
        if key not in defaults:
            continue
        normalized = colors.to_hex(colors.parse(value))
        if normalized != defaults[key]:
            out[key] = normalized
    return out


def _map_lightness(value: float, old: float, new: float) -> float:
    if value >= old:
        if old >= 1:
            return new
        return new + (value - old) * (1 - new) / (1 - old)
    if old <= 0:
        return new
    return value * new / old


def _shift(color: colors.RGBA, old: colors.RGBA, new: colors.RGBA) -> colors.RGBA:
    th, ts, tl = colors.to_hsl(color)
    oh, os_, ol = colors.to_hsl(old)
    nh, ns, nl = colors.to_hsl(new)
    if ts < 0.05:
        # A grey token (e.g. a chrome border): adopt the seed's hue outright.
        th, ts_out = nh, ns * (ts / os_ if os_ > 0.05 else 1.0)
    else:
        th = th + (nh - oh)
        ts_out = ts * (ns / os_) if os_ > 0.05 else ns
    return colors.from_hsl(th, ts_out, _map_lightness(tl, ol, nl), color[3])


def _neutral(
    color: colors.RGBA,
    anchors: list[tuple[float, colors.RGBA]],
) -> colors.RGBA:
    """Piecewise interpolate by original lightness between anchor colours."""
    _h, _s, tl = colors.to_hsl(color)
    for (l0, c0), (l1, c1) in zip(anchors, anchors[1:], strict=False):
        if l0 <= tl <= l1:
            t = 0.0 if l1 == l0 else (tl - l0) / (l1 - l0)
            out = colors.mix(c0, c1, t)
            return (*out[:3], color[3])
    return color


def _neutral_anchors(
    old_bg: colors.RGBA,
    new_bg: colors.RGBA,
    old_text: colors.RGBA,
    new_text: colors.RGBA,
) -> list[tuple[float, colors.RGBA]]:
    points = {
        colors.to_hsl(old_bg)[2]: new_bg,
        colors.to_hsl(old_text)[2]: new_text,
    }
    points.setdefault(0.0, (0.0, 0.0, 0.0, 1.0))
    points.setdefault(1.0, (255.0, 255.0, 255.0, 1.0))
    return sorted(points.items())


def derive_tokens(seeds: dict, mode: str) -> dict[str, str]:
    """Return ``{token: hex}`` for every token changed by the seeds."""
    active = effective_seeds(seeds, mode)
    if not active:
        return {}
    defaults = {k: colors.parse(v) for k, v in seed_defaults(mode).items()}
    new = {k: colors.parse(v) for k, v in active.items()}

    neutral_anchors = None
    if "background" in new or "text" in new:
        neutral_anchors = _neutral_anchors(
            defaults["background"],
            new.get("background", defaults["background"]),
            defaults["text"],
            new.get("text", defaults["text"]),
        )

    out: dict[str, str] = {}
    for name, token in color_tokens().items():
        family = token.family(mode)
        original = colors.parse(token.default(mode))
        if family == FAMILY_NEUTRAL:
            if neutral_anchors is None:
                continue
            result = _neutral(original, neutral_anchors)
        elif family == FAMILY_CHROME:
            if "chrome" not in new:
                continue
            result = _shift(original, defaults["chrome"], new["chrome"])
        elif family in new:
            result = _shift(original, defaults[family], new[family])
        else:
            continue
        value = colors.to_hex(result)
        if value != colors.to_hex(original):
            out[name] = value
    return out
