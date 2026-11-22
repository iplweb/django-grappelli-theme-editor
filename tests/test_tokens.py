import sys
from pathlib import Path

import grappelli

from grappelli_theme_editor import tokens, tokens_data

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "extract_tokens.py"


def _extract():
    import importlib.util

    spec = importlib.util.spec_from_file_location("extract_tokens", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses need the module registered
    spec.loader.exec_module(module)
    css = (
        Path(grappelli.__file__).parent / "static/grappelli/stylesheets/screen.css"
    ).read_text(encoding="utf-8")
    return module.extract(css)


def test_tokens_data_matches_installed_grappelli():
    """Fails after a Grappelli upgrade: run scripts/extract_tokens.py."""
    data = _extract()
    assert data["light"] == tokens_data.LIGHT_DEFAULTS
    assert data["dark"] == tokens_data.DARK_DEFAULTS
    assert data["font_family"] == tokens_data.FONT_FAMILY_DECLS
    assert data["font_size"] == tokens_data.FONT_SIZE_DECLS
    assert data["radius"] == tokens_data.RADIUS_DECLS
    assert data["padding"] == tokens_data.PADDING_DECLS


def test_every_token_has_group_and_both_modes():
    all_tokens = tokens.all_tokens()
    assert len(all_tokens) > 150
    groups = {key for key, _label in tokens.GROUPS} | {"images"}
    for token in all_tokens.values():
        assert token.group in groups
        assert token.light and token.dark


def test_seed_reference_tokens_belong_to_their_family():
    t = tokens.color_tokens()
    assert t["--grp-link-color"].family_light == "accent"
    assert t["--grp-dark-background-color"].family_light == "chrome"
    assert t["--grp-body-background-color"].family_light == "neutral"
    assert t["--grp-mark-background-color"].family_light == "keep"
