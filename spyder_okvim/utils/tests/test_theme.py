"""Color choices remain readable for unrecognized or low-contrast themes."""

import pytest
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QPlainTextEdit

from spyder_okvim.utils.theme import (
    contrast_ratio,
    occurrence_colors,
    readable_color,
    selection_colors,
)


@pytest.mark.parametrize(
    "foreground, background, expected",
    [
        ("#000000", "#ffffff", 21.0),
        ("#ffffff", "#000000", 21.0),
        ("#123456", "#123456", 1.0),
        ("#777777", "#ffffff", 4.4781),
        (QColor(255, 255, 255, 0), "#000000", 1.0),
    ],
)
def test_known_relative_luminance_ratios(foreground, background, expected):
    assert contrast_ratio(foreground, background) == pytest.approx(expected, abs=0.001)


def test_theme_colors_take_priority_over_neutral_fallbacks():
    assert readable_color("#78d7e8", "#101010", "#eeeeee") == QColor("#78d7e8")
    assert readable_color("#37aefe", "#fafafa", "#333333") == QColor("#333333")
    assert (
        contrast_ratio(readable_color("#eeeeee", "#ffffff", "#dddddd"), "#ffffff")
        >= 4.5
    )
    assert readable_color(QColor(), "#ffffff", "#333333") == QColor("#333333")


def test_translucent_highlights_use_the_actual_editor_background(qtbot):
    editor = QPlainTextEdit()
    qtbot.addWidget(editor)
    palette = QPalette(editor.palette())
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.Text, QColor("#111111"))
    palette.setColor(QPalette.Highlight, QColor(0, 0, 0, 128))
    palette.setColor(QPalette.HighlightedText, QColor("#777777"))
    editor.setPalette(palette)
    foreground, background = selection_colors(editor)
    assert background == QColor("#7f7f7f")
    assert contrast_ratio(foreground, background) >= 4.5
    editor.occurrence_color = QColor(0, 0, 0, 0)
    foreground, background = occurrence_colors(editor)
    assert background == QColor("#ffffff")
    assert foreground == QColor("#111111")
    editor.occurrence_color = QColor()
    assert occurrence_colors(editor) == selection_colors(editor)
