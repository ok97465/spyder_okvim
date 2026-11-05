"""Status text follows Spyder even when native Qt colors use another theme."""

import pytest
import qdarkstyle
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QWidget
from spyder.config.manager import CONF
from spyder.utils import palette as spyder_palette

from spyder_okvim.spyder.vim_widgets import VimMessageLabel, VimStateLabel
from spyder_okvim.utils.theme import contrast_ratio, interface_palette


@pytest.fixture
def mode_colors(monkeypatch):
    """Keep configured mode overrides local to each test."""
    options = {"mode_fg_color": "", "mode_bg_color": ""}
    original = CONF.get

    def get(section, option, *args, **kwargs):
        if option in options:
            return options[option]
        return original(section, option, *args, **kwargs)

    monkeypatch.setattr(CONF, "get", get)
    return options


@pytest.mark.parametrize("dark", [True, False])
def test_status_uses_interface_colors_with_opposite_native_palette(
    qtbot, qapp, monkeypatch, mode_colors, dark
):
    theme = (
        spyder_palette.SpyderPaletteDark if dark else spyder_palette.SpyderPaletteLight
    )
    monkeypatch.setattr(spyder_palette, "SpyderPalette", theme)
    stylesheet = qapp.styleSheet()
    try:
        qapp.setStyleSheet(qdarkstyle.load_stylesheet(palette=theme))
        parent = QWidget()
        qtbot.addWidget(parent)
        native = QPalette(parent.palette())
        native.setColor(QPalette.Window, QColor("white" if dark else "#202020"))
        native.setColor(QPalette.WindowText, QColor("black" if dark else "white"))
        native.setColor(QPalette.Highlight, QColor("#ffffee"))
        native.setColor(QPalette.HighlightedText, QColor("white"))
        native.setColor(QPalette.Mid, QColor("white" if dark else "black"))
        parent.setPalette(native)

        mode = VimStateLabel(parent)
        message = VimMessageLabel(parent)
        message.setText("검색 상태 · search status")
        parent.show()
        mode.ensurePolished()
        message.ensurePolished()
        expected = interface_palette(parent)
        assert (
            f"border: 1px solid {expected.color(QPalette.Mid).name()};"
            in mode.styleSheet()
        )
        assert (
            f"background-color: {QColor(theme.COLOR_ACCENT_2).name()};"
            in mode.styleSheet()
        )
        for group in (QPalette.Active, QPalette.Inactive):
            assert message.palette().color(group, QPalette.WindowText) == (
                expected.color(group, QPalette.WindowText)
            )
        assert message.palette().color(QPalette.Disabled, QPalette.WindowText) == (
            QColor(theme.COLOR_DISABLED)
        )
        assert message.text() == "검색 상태 · search status"
        assert message.accessibleDescription() == message.text()
    finally:
        qapp.setStyleSheet(stylesheet)


def test_mode_default_foreground_is_readable_on_custom_background(qtbot, mode_colors):
    mode_colors["mode_bg_color"] = "#ffffff"
    parent = QWidget()
    qtbot.addWidget(parent)
    label = VimStateLabel(parent)
    palette = QPalette(label.palette())
    palette.setColor(QPalette.HighlightedText, QColor("#eeeeee"))
    palette.setColor(QPalette.Text, QColor("#222222"))
    label.setPalette(palette)
    label.ensurePolished()
    assert "color: #222222;" in label.styleSheet()
    assert contrast_ratio("#222222", "#ffffff") >= 4.5

    mode_colors["mode_fg_color"] = "#eeeeee"
    label.refresh_appearance()
    assert "color: #eeeeee;" in label.styleSheet()


def test_message_accepts_later_explicit_palette(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    message = VimMessageLabel(parent)
    palette = QPalette(message.palette())
    palette.setColor(QPalette.WindowText, QColor("#123456"))
    message.setPalette(palette)
    message.ensurePolished()
    assert message.palette().color(QPalette.WindowText) == QColor("#123456")
