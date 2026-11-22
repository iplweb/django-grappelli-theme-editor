from grappelli_theme_editor import colors
from grappelli_theme_editor.palette import derive_tokens, effective_seeds


def test_no_seeds_changes_nothing():
    assert derive_tokens({}, "light") == {}
    assert derive_tokens({"light": {}, "dark": {}}, "dark") == {}


def test_seed_equal_to_default_is_ignored():
    assert effective_seeds({"light": {"accent": "#309BBF"}}, "light") == {}


def test_accent_lands_exactly_on_reference_token():
    out = derive_tokens({"light": {"accent": "#8e44ad"}}, "light")
    assert out["--grp-link-color"] == "#8e44ad"
    # the whole family moves, not just one token
    assert "--grp-form-button-background-color" in out
    # neutral greys are untouched by an accent change
    assert "--grp-body-background-color" not in out


def test_background_and_text_remap_neutrals():
    out = derive_tokens(
        {"light": {"background": "#f5f2ed", "text": "#222222"}}, "light"
    )
    assert out["--grp-body-background-color"] == "#f5f2ed"
    assert out["--grp-font-color"] == "#222222"
    assert "--grp-module-background-color" in out


def test_dark_accent_is_derived_and_readable():
    seeds = {"light": {"accent": "#4f5bd5"}, "dark": {"background": "#0d1117"}}
    dark = effective_seeds(seeds, "dark")
    assert "accent" in dark
    ratio = colors.contrast_ratio(colors.parse(dark["accent"]), colors.parse("#0d1117"))
    assert ratio >= 4.5


def test_explicit_dark_seed_wins_over_derivation():
    seeds = {"light": {"accent": "#4f5bd5"}, "dark": {"accent": "#ff00ff"}}
    assert effective_seeds(seeds, "dark")["accent"] == "#ff00ff"
