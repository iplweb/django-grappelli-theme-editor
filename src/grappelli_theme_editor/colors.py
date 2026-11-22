"""Small, dependency-free colour toolkit: parsing, HSL maths, WCAG contrast.

Only what the theme editor needs. Colours are handled as ``(r, g, b, a)``
tuples with r/g/b in 0..255 (floats allowed internally) and a in 0..1.
"""

from __future__ import annotations

import colorsys
import re

RGBA = tuple[float, float, float, float]

NAMED_COLORS: dict[str, str] = {
    # The subset of CSS named colours that Grappelli itself uses, plus the
    # obvious ones people type. Anything else is accepted by the validator
    # (browsers know all 148 names) but cannot be fed into palette maths.
    "white": "#ffffff",
    "black": "#000000",
    "red": "#ff0000",
    "green": "#008000",
    "blue": "#0000ff",
    "gray": "#808080",
    "grey": "#808080",
    "silver": "#c0c0c0",
    "navy": "#000080",
    "teal": "#008080",
    "orange": "#ffa500",
    "yellow": "#ffff00",
    "purple": "#800080",
    "maroon": "#800000",
    "olive": "#808000",
    "transparent": "#00000000",
}

_HEX_RE = re.compile(r"^#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
# Unambiguous grammar (no adjacent optional-whitespace quantifiers, which
# backtrack badly on malformed input): numbers are separated either by a
# comma with optional spaces or by plain spaces, alpha by "," or "/".
_N = r"(-?(?:\d{1,4}(?:\.\d{0,4})?|\.\d{1,4}))(%?)"
_SEP = r"(?: ?, ?| )"
_ASEP = r"(?: ?[,/] ?)"
_FUNC_RE = re.compile(
    rf"^(rgba?|hsla?)\( ?{_N}{_SEP}{_N}{_SEP}{_N}(?:{_ASEP}{_N})? ?\)$",
    re.IGNORECASE,
)
MAX_COLOR_LENGTH = 40

# All CSS named colours (CSS Color Module Level 4), plus keywords.
CSS_COLOR_NAMES = frozenset(
    """aliceblue antiquewhite aqua aquamarine azure beige bisque black
    blanchedalmond blue blueviolet brown burlywood cadetblue chartreuse
    chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan
    darkgoldenrod darkgray darkgreen darkgrey darkkhaki darkmagenta
    darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen
    darkslateblue darkslategray darkslategrey darkturquoise darkviolet
    deeppink deepskyblue dimgray dimgrey dodgerblue firebrick floralwhite
    forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray green
    greenyellow grey honeydew hotpink indianred indigo ivory khaki lavender
    lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan
    lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon
    lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue
    lightyellow lime limegreen linen magenta maroon mediumaquamarine
    mediumblue mediumorchid mediumpurple mediumseagreen mediumslateblue
    mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream
    mistyrose moccasin navajowhite navy oldlace olive olivedrab orange
    orangered orchid palegoldenrod palegreen paleturquoise palevioletred
    papayawhip peachpuff peru pink plum powderblue purple rebeccapurple red
    rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell sienna
    silver skyblue slateblue slategray slategrey snow springgreen steelblue
    tan teal thistle tomato turquoise violet wheat white whitesmoke yellow
    yellowgreen transparent currentcolor""".split()
)


class ColorError(ValueError):
    pass


def is_valid_css_color(value: str) -> bool:
    """Check used by model validation: hex, rgb()/hsl() or a CSS colour name."""
    value = value.strip()
    if len(value) > MAX_COLOR_LENGTH:
        return False
    return bool(
        _HEX_RE.match(value)
        or _FUNC_RE.match(value)
        or value.lower() in CSS_COLOR_NAMES
    )


def parse(value: str) -> RGBA:
    value = value.strip().lower()
    if len(value) > MAX_COLOR_LENGTH:
        raise ColorError("Colour value too long")
    if value in NAMED_COLORS:
        value = NAMED_COLORS[value]
    m = _HEX_RE.match(value)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return (r, g, b, a)
    m = _FUNC_RE.match(value)
    if m:
        kind = m.group(1).lower()
        nums = [m.group(i) for i in (2, 4, 6, 8)]
        pcts = [m.group(i) for i in (3, 5, 7, 9)]
        alpha = 1.0
        if nums[3] is not None:
            alpha = float(nums[3]) / (100 if pcts[3] else 1)
        if kind.startswith("rgb"):
            rgb = [
                float(n) * 2.55 if p else float(n)
                for n, p in zip(nums[:3], pcts[:3], strict=True)
            ]
            return (*rgb, alpha)
        h = float(nums[0]) % 360 / 360
        s = float(nums[1]) / 100
        l_ = float(nums[2]) / 100
        r, g, b = colorsys.hls_to_rgb(h, l_, s)
        return (r * 255, g * 255, b * 255, alpha)
    raise ColorError(f"Unsupported colour: {value!r}")


def to_hex(c: RGBA) -> str:
    r, g, b, a = c
    channels = [round(max(0.0, min(255.0, x))) for x in (r, g, b)]
    out = "#" + "".join(f"{x:02x}" for x in channels)
    if a < 1:
        out += f"{round(max(0.0, min(1.0, a)) * 255):02x}"
    return out


def to_hsl(c: RGBA) -> tuple[float, float, float]:
    """Return (hue 0..360, saturation 0..1, lightness 0..1)."""
    h, l_, s = colorsys.rgb_to_hls(c[0] / 255, c[1] / 255, c[2] / 255)
    return (h * 360, s, l_)


def from_hsl(h: float, s: float, l_: float, a: float = 1.0) -> RGBA:
    s = max(0.0, min(1.0, s))
    l_ = max(0.0, min(1.0, l_))
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, l_, s)
    return (r * 255, g * 255, b * 255, a)


def mix(a: RGBA, b: RGBA, t: float) -> RGBA:
    """Linear interpolation in sRGB, t=0 → a, t=1 → b."""
    t = max(0.0, min(1.0, t))
    return tuple(x + (y - x) * t for x, y in zip(a, b, strict=True))  # type: ignore[return-value]


def _channel_luminance(v: float) -> float:
    v /= 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def relative_luminance(c: RGBA) -> float:
    r, g, b = (_channel_luminance(x) for x in c[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: RGBA, bg: RGBA) -> float:
    """WCAG 2.x contrast ratio (1..21). Alpha is composited over ``bg``."""
    if fg[3] < 1:
        fg = mix(bg, (*fg[:3], 1.0), fg[3])
    la, lb = relative_luminance(fg), relative_luminance(bg)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)
