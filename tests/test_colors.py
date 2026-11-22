import pytest

from grappelli_theme_editor import colors


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("#fff", "#ffffff"),
        ("#ABCDEF", "#abcdef"),
        ("white", "#ffffff"),
        ("rgb(255, 0, 0)", "#ff0000"),
        ("rgba(0,0,255,.5)", "#0000ff80"),
        ("hsl(120, 100%, 25%)", "#008000"),
        ("#11223344", "#11223344"),
    ],
)
def test_parse_and_format(value, expected):
    assert colors.to_hex(colors.parse(value)) == expected


def test_parse_rejects_garbage():
    with pytest.raises(colors.ColorError):
        colors.parse("not-a-colour(1)")


def test_contrast_ratio_extremes():
    black, white = colors.parse("#000"), colors.parse("#fff")
    assert colors.contrast_ratio(black, white) == pytest.approx(21, rel=1e-3)
    assert colors.contrast_ratio(white, white) == pytest.approx(1)


def test_hsl_roundtrip():
    c = colors.parse("#309bbf")
    h, s, l_ = colors.to_hsl(c)
    assert colors.to_hex(colors.from_hsl(h, s, l_)) == "#309bbf"
