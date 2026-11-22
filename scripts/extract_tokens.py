#!/usr/bin/env python
"""Regenerate ``src/grappelli_theme_editor/tokens_data.py`` from Grappelli's CSS.

Grappelli 5 defines its whole palette as CSS custom properties in three
blocks of ``grappelli/stylesheets/screen.css``:

* ``:root{...}``                    — light mode,
* ``html[data-theme=dark]{...}``    — dark mode (forced by the toggle),
* ``@media(prefers-color-scheme: dark){html[data-theme=auto]{...}}`` — dark
  mode following the OS.

Fonts and corner radii, on the other hand, are hardcoded. This script also
collects the selectors that declare them, so the theme editor can emit
targeted overrides instead of shipping a patched copy of ``screen.css``.

Usage::

    uv run python scripts/extract_tokens.py            # installed grappelli
    uv run python scripts/extract_tokens.py path/to/screen.css
"""

from __future__ import annotations

import pprint
import re
import sys
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "grappelli_theme_editor"
    / "tokens_data.py"
)

PADDING_RE = re.compile(r"^padding(?:-(?:top|right|bottom|left))?$")
RADIUS_RE = re.compile(
    r"^border(?:-(?:top|bottom)-(?:left|right))?-radius$",
)


@dataclass
class Rule:
    media: str | None
    selector: str
    declarations: list[tuple[str, str]]


def _split_declarations(body: str) -> list[tuple[str, str]]:
    out = []
    # Values never contain ';' in Grappelli's minified CSS except inside
    # url(data:...) which it does not use, so a plain split is safe.
    for chunk in body.split(";"):
        if ":" not in chunk:
            continue
        prop, value = chunk.split(":", 1)
        out.append((prop.strip(), value.strip()))
    return out


def parse_rules(css: str) -> list[Rule]:
    """Tiny brace-depth parser: enough for Grappelli's flat, minified CSS.

    Returns style rules with the enclosing ``@media`` prelude (one level of
    nesting is all Grappelli uses). ``@font-face``/``@keyframes`` bodies are
    skipped.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    rules: list[Rule] = []
    i = 0
    media: str | None = None
    media_depth = 0
    depth = 0
    start = 0
    while i < len(css):
        ch = css[i]
        if ch == "{":
            prelude = css[start:i].strip()
            if prelude.startswith("@media"):
                media = prelude
                media_depth = depth + 1
                depth += 1
                start = i + 1
            elif prelude.startswith("@"):
                # skip the whole at-rule block
                level = 1
                j = i + 1
                while level and j < len(css):
                    if css[j] == "{":
                        level += 1
                    elif css[j] == "}":
                        level -= 1
                    j += 1
                i = j
                start = i
                continue
            else:
                end = css.index("}", i)
                rules.append(
                    Rule(media, prelude, _split_declarations(css[i + 1 : end]))
                )
                i = end + 1
                start = i
                continue
        elif ch == "}":
            depth -= 1
            if media is not None and depth < media_depth:
                media = None
            start = i + 1
        elif ch == ";" and depth == 0:
            # top-level @charset / @import
            start = i + 1
        i += 1
    return rules


def _vars(rule: Rule) -> dict[str, str]:
    return {p: v for p, v in rule.declarations if p.startswith("--grp-")}


def extract(css: str) -> dict:
    rules = parse_rules(css)
    light = dark = auto = None
    for r in rules:
        if r.selector == ":root" and _vars(r):
            light = _vars(r)
        elif r.selector == "html[data-theme=dark]" and _vars(r):
            dark = _vars(r)
        elif r.selector == "html[data-theme=auto]" and _vars(r):
            auto = _vars(r)
    if not (light and dark):
        raise SystemExit("Could not find Grappelli's --grp-* variable blocks.")
    if auto is not None and auto != dark:
        print(
            "WARNING: auto-dark block differs from data-theme=dark block",
            file=sys.stderr,
        )

    # Every declaration of the properties the layer re-declares, in source
    # order. The layer must replay *all* of them (not just the ones it
    # rewrites) and in the same order, otherwise re-declaring an early rule
    # after Grappelli's sheet would beat a later rule of equal specificity.
    font_family: list[tuple[str, str, str]] = []
    font_size: list[tuple[str, str, str]] = []
    radius: list[tuple[str, str, str, str]] = []
    padding: list[tuple[str, str, str, str]] = []
    for r in rules:
        if r.media and "prefers-color-scheme" in r.media:
            continue
        key_media = r.media or ""
        for prop, value in r.declarations:
            if "!important" in value:
                continue  # wins regardless of order; leave it alone
            if prop == "font-family":
                font_family.append((key_media, r.selector, value))
            elif prop == "font-size":
                font_size.append((key_media, r.selector, value))
            elif RADIUS_RE.match(prop):
                radius.append((key_media, r.selector, prop, value))
            elif PADDING_RE.match(prop):
                padding.append((key_media, r.selector, prop, value))

    return {
        "light": light,
        "dark": dark,
        "font_family": font_family,
        "font_size": font_size,
        "radius": radius,
        "padding": padding,
    }


def render(data: dict, grappelli_version: str) -> str:
    def fmt(obj) -> str:
        return pprint.pformat(obj, width=88, sort_dicts=True)

    return (
        '"""GENERATED by scripts/extract_tokens.py — do not edit by hand.\n\n'
        f"Source: django-grappelli {grappelli_version}, "
        "grappelli/stylesheets/screen.css\n"
        '"""\n\n'
        f"GRAPPELLI_VERSION = {grappelli_version!r}\n\n"
        f"LIGHT_DEFAULTS = {fmt(data['light'])}\n\n"
        f"DARK_DEFAULTS = {fmt(data['dark'])}\n\n"
        "# Source-ordered declarations: (media prelude or '', selector, value)\n"
        f"FONT_FAMILY_DECLS = {fmt(data['font_family'])}\n\n"
        f"FONT_SIZE_DECLS = {fmt(data['font_size'])}\n\n"
        "# (media prelude or '', selector, property, value)\n"
        f"RADIUS_DECLS = {fmt(data['radius'])}\n\n"
        "# (media prelude or '', selector, property, value)\n"
        f"PADDING_DECLS = {fmt(data['padding'])}\n"
    )


def main(argv: list[str]) -> None:
    if len(argv) > 1:
        css_path = Path(argv[1])
        grappelli_version = argv[2] if len(argv) > 2 else "unknown"
    else:
        import grappelli

        css_path = (
            Path(grappelli.__file__).parent / "static/grappelli/stylesheets/screen.css"
        )
        grappelli_version = version("django-grappelli")
    data = extract(css_path.read_text(encoding="utf-8"))
    OUTPUT.write_text(render(data, grappelli_version), encoding="utf-8")
    print(
        f"Wrote {OUTPUT} — {len(data['light'])} tokens, "
        f"{len(data['font_family'])} font-family / "
        f"{len(data['font_size'])} font-size / "
        f"{len(data['radius'])} radius / "
        f"{len(data['padding'])} padding declarations"
    )


if __name__ == "__main__":
    main(sys.argv)
