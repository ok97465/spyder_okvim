"""Spyder dependency teardown and appearance callbacks release shared UI."""

# Standard Libraries
from types import SimpleNamespace
from unittest.mock import Mock

# Third Party Libraries
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QMainWindow
from spyder.api.fonts import SpyderFontType
from spyder.api.plugins import Plugins

# Project Libraries
from spyder_okvim.spyder.plugin import OkVim, StatusBarVimWidget


def test_preferences_teardown_deregisters_plugin_page():
    preferences = Mock()
    plugin = SimpleNamespace(get_plugin=Mock(return_value=preferences))
    OkVim.on_preferences_teardown(plugin)
    plugin.get_plugin.assert_called_once_with(Plugins.Preferences)
    preferences.deregister_plugin_preferences.assert_called_once_with(plugin)


def test_statusbar_teardown_releases_id_once_and_allows_reuse(vim_bot, qtbot):
    main, _, _, plugin, _ = vim_bot
    statusbar = main.status_bar
    widget = plugin._status_bar_widget
    try:
        assert statusbar.STATUS_WIDGETS[StatusBarVimWidget.ID] is widget
        plugin.on_statusbar_teardown()
        assert StatusBarVimWidget.ID not in statusbar.STATUS_WIDGETS
        assert widget.isHidden()
        plugin.on_statusbar_teardown()
        assert not plugin._statusbar_attached
        plugin._sync_statusbar()
        assert StatusBarVimWidget.ID not in statusbar.STATUS_WIDGETS
        assert widget.isHidden()
        window = QMainWindow()
        qtbot.addWidget(window)
        plugin._move_statusbar(window.statusBar())
        assert widget.parentWidget() is statusbar
        assert widget.isHidden()
        # Spyder's StatusBar rejects duplicate IDs when a plugin is re-enabled.
        statusbar.add_status_widget(widget)
        assert statusbar.STATUS_WIDGETS[StatusBarVimWidget.ID] is widget
    finally:
        if StatusBarVimWidget.ID not in statusbar.STATUS_WIDGETS:
            statusbar.add_status_widget(widget)
        plugin._statusbar_attached = True
        widget.show()


def test_update_font_uses_current_spyder_monospace_font(vim_bot, monkeypatch):
    _, _, _, plugin, _ = vim_bot
    line = plugin.vim_cmd.commandline
    previous = QFont(line.font())
    configured = QFont("Courier New", 16)
    get_font = Mock(return_value=configured)
    monkeypatch.setattr(plugin, "get_font", get_font)
    try:
        plugin.update_font()
        get_font.assert_called_once_with(SpyderFontType.Monospace)
        assert line.font().family() == configured.family()
        assert line.font().pointSize() == configured.pointSize()
    finally:
        line.setFont(previous)
