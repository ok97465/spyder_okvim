"""Readable Qt roles from Spyder's interface theme instead of native colors."""

import pytest
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QWidget
from spyder.utils import palette as spyder_palette

from spyder_okvim.utils.theme import (
    contrast_ratio,
    interface_palette,
    readable_color,
    selection_colors,
)


def test_contrast_uses_srgb_and_composites_translucent_foreground():
    assert contrast_ratio("black", "white") == pytest.approx(21.0)
    assert contrast_ratio("#333333", "#333333") == pytest.approx(1.0)
    assert contrast_ratio(QColor(), "white") == 0
    assert 5 < contrast_ratio(QColor(255, 255, 255, 128), "black") < 6


def test_readable_color_keeps_preferred_and_prioritizes_theme_fallback():
    assert readable_color("#223344", "white", "black") == QColor("#223344")
    assert readable_color("#aaaaaa", "white", "#223344") == QColor("#223344")
    assert readable_color("#aaaaaa", "white", minimum_ratio=22) == QColor("black")


@pytest.mark.parametrize(
    "palette_class, dark",
    [
        (spyder_palette.SpyderPaletteDark, True),
        (spyder_palette.SpyderPaletteLight, False),
    ],
)
def test_interface_roles_use_spyder_in_all_color_groups(
    qtbot, monkeypatch, palette_class, dark
):
    widget = QWidget()
    qtbot.addWidget(widget)
    native = QPalette(widget.palette())
    native.setColor(QPalette.Base, QColor("white"))
    native.setColor(QPalette.Mid, QColor("white"))
    native.setColor(QPalette.Text, QColor("black"))
    widget.setPalette(native)
    monkeypatch.setattr(spyder_palette, "SpyderPalette", palette_class)
    palette = interface_palette(widget)
    for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
        background = palette.color(group, QPalette.Base)
        foreground = palette.color(group, QPalette.Text)
        assert (background.lightness() < 128) == dark
        assert background == QColor(palette_class.COLOR_BACKGROUND_1)
        assert palette.color(group, QPalette.Mid) == QColor(
            palette_class.COLOR_BACKGROUND_4
        )
        assert contrast_ratio(foreground, background) >= (
            3.0 if group == QPalette.Disabled else 4.5
        )
        assert palette.color(group, QPalette.Highlight) == QColor(
            palette_class.COLOR_ACCENT_2
        )
        assert (
            contrast_ratio(
                palette.color(group, QPalette.HighlightedText),
                palette.color(group, QPalette.Highlight),
            )
            >= 4.5
        )
    assert widget.palette().color(QPalette.Mid) == QColor("white")


def test_selection_composites_highlight_and_finds_readable_text(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    palette = QPalette(widget.palette())
    palette.setColor(QPalette.Base, QColor("#222222"))
    palette.setColor(QPalette.Text, QColor("white"))
    palette.setColor(QPalette.Highlight, QColor(20, 120, 220, 128))
    palette.setColor(QPalette.HighlightedText, QColor("#222222"))
    widget.setPalette(palette)
    foreground, background = selection_colors(widget)
    assert background.alpha() == 255
    assert foreground == QColor("white")
    assert contrast_ratio(foreground, background) >= 4.5
