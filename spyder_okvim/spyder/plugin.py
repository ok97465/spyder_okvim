# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) Spyder Project Contributors
#
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
# -----------------------------------------------------------------------------
"""OkVim Plugin."""

# Third Party Libraries
import qtawesome as qta
from qtpy.QtCore import Qt, Signal, QCoreApplication
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import QHBoxLayout, QMainWindow, QShortcut
from spyder.api.plugin_registration.decorators import on_plugin_available
from spyder.api.plugins import Plugins, SpyderDockablePlugin

# Project Libraries
from spyder_okvim.utils.testing_env import running_in_pytest
from spyder.api.widgets.status import StatusBarWidget
from spyder.utils.icon_manager import MAIN_FG_COLOR

# Project Libraries
from spyder_okvim.spyder.api import CustomLayout
from spyder_okvim.spyder.config import CONF_DEFAULTS, CONF_SECTION, CONF_VERSION
from spyder_okvim.spyder.confpage import OkvimConfigPage
from spyder_okvim.spyder.vim_widgets import VimPane, VimWidget


class StatusBarVimWidget(StatusBarWidget):
    """Status bar widget for okvim."""

    ID = f"{CONF_SECTION}_status_bar"

    def __init__(self, parent, msg_label, status_label, cmd_line):
        """Initialize status bar widget.

        Args:
            parent: Parent widget for this status bar widget.
            msg_label: Label used to display messages.
            status_label: Label showing the current Vim mode.
            cmd_line: Line edit used for entering commands.
        """
        self.msg_label = msg_label
        self.status_label = status_label
        self.cmd_line = cmd_line
        super().__init__(parent, show_icon=False, show_label=False)

    # ---- Private API -------------------------------------------------
    def _set_layout(self):
        """Create the internal layout of the status bar widget."""
        spacing_post = 12
        spacing = 5

        self.msg_label.setMinimumWidth(90)
        self.cmd_line.setMinimumWidth(80)
        width_msg = self.msg_label.sizeHint().width()
        width_status = self.status_label.sizeHint().width()
        width_cmd = self.cmd_line.sizeHint().width()

        width_total = width_msg + width_status + width_cmd

        layout = QHBoxLayout(self)
        layout.setSpacing(spacing)
        layout.addWidget(self.msg_label, int(width_msg / width_total * 100))
        layout.addWidget(self.status_label, int(width_status / width_total * 100))
        layout.addWidget(self.cmd_line, int(width_cmd / width_total * 100))
        layout.addSpacing(spacing_post)
        layout.setContentsMargins(0, 0, 0, 0)

        width_total += 2 * spacing + spacing_post
        self.setFixedWidth(width_total)
        self.setLayout(layout)

    def set_layout(self):
        """Public entry point to apply the layout."""
        self._set_layout()

    # ---- Status bar widget API
    def set_icon(self):
        """Set the icon for the status bar widget."""
        pass

    def set_value(self, value):
        """Set formatted text value."""
        pass

    def update_tooltip(self):
        """Update tooltip for widget."""
        pass

    def mouseReleaseEvent(self, event):
        """Override Qt method to allow for click signal."""
        super().mouseReleaseEvent(event)

    # ---- API to be defined by user
    def get_tooltip(self):
        """Return the widget tooltip text."""
        return ""

    def get_icon(self):
        """Return the widget icon."""
        return None


class OkVim(SpyderDockablePlugin):  # pylint: disable=R0904
    """Implements a Vim-like command mode."""

    focus_changed = Signal()
    NAME = CONF_SECTION
    REQUIRES = [Plugins.StatusBar, Plugins.Preferences]
    OPTIONAL = [Plugins.Editor]
    WIDGET_CLASS = VimPane
    CONF_SECTION = CONF_SECTION
    CONF_WIDGET_CLASS = OkvimConfigPage
    CONF_DEFAULTS = CONF_DEFAULTS
    CONF_ = CONF_VERSION
    CUSTOM_LAYOUTS = [CustomLayout]
    CAN_BE_DISABLED = True
    RAISE_AND_FOCUS = True

    @property
    def vim_cmd(self):
        """Return vim_cmd for test."""
        return self.get_widget().vim_cmd

    # --- SpyderDockablePlugin API
    # ------------------------------------------------------------------------
    @staticmethod
    def get_name() -> str:
        """Return name."""
        return CONF_SECTION

    @staticmethod
    def get_description() -> str:
        """Return description."""
        return "A plugin for Spyder to enable Vim keybindings"

    @classmethod
    def get_icon(cls):
        """Return widget icon."""
        return qta.icon("mdi.vimeo", color=MAIN_FG_COLOR)

    def on_initialize(self) -> None:
        """Perform plugin initialization after it is added to Spyder."""
        vim_cmd = self.get_widget().vim_cmd

        status_bar_widget = StatusBarVimWidget(
            self._main,
            vim_cmd.msg_label,
            vim_cmd.status_label,
            vim_cmd.commandline,
        )

        statusbar_plugin = self.get_plugin(Plugins.StatusBar)
        self._statusbar_plugin = statusbar_plugin
        self._status_bar_widget = status_bar_widget
        self._current_statusbar = getattr(statusbar_plugin, "_statusbar", statusbar_plugin)
        statusbar_plugin.add_status_widget(self._status_bar_widget)

        editorsplitter = vim_cmd.editor_widget.get_widget().editorsplitter
        self._esc_shortcuts = {}
        self._install_shortcut(editorsplitter)

        editor = self.get_plugin(Plugins.Editor, error=False)
        if editor is not None and hasattr(editor, "sig_editor_focus_changed"):
            editor.sig_editor_focus_changed.connect(self._on_editor_focus_changed)

    # ---- Private helpers -------------------------------------------------
    def _install_shortcut(self, editorsplitter):
        """Install ESC shortcut on the given editor splitter if needed."""
        if editorsplitter in getattr(self, "_esc_shortcuts", {}):
            return
        esc = QShortcut(
            QKeySequence("Esc"),
            editorsplitter,
            self.get_widget().vim_cmd.commandline.setFocus,
        )
        esc.setContext(Qt.WidgetWithChildrenShortcut)
        self._esc_shortcuts[editorsplitter] = esc

    def _on_editor_focus_changed(self):
        """Move Vim widgets when the focused editor changes."""
        vim_cmd = self.get_widget().vim_cmd
        editor_widget = vim_cmd.editor_widget.get_widget()
        editorstack = editor_widget.get_current_editorstack()
        if editorstack is None:
            return

        editorsplitter = editorstack.parent()
        self._install_shortcut(editorsplitter)

        window = editorsplitter.window()
        main_statusbar = getattr(self._statusbar_plugin, "_statusbar", self._statusbar_plugin)
        new_statusbar = (
            window.statusBar()
            if isinstance(window, QMainWindow) and window is not self._main
            else main_statusbar
        )

        if new_statusbar is self._current_statusbar:
            return

        if self._current_statusbar is main_statusbar:
            if hasattr(self._statusbar_plugin, "remove_status_widget"):
                try:
                    self._statusbar_plugin.remove_status_widget(
                        self._status_bar_widget.ID
                    )
                except Exception:
                    pass
            else:
                self._current_statusbar.removeWidget(self._status_bar_widget)
        elif self._current_statusbar is not None:
            self._current_statusbar.removeWidget(self._status_bar_widget)

        if new_statusbar is main_statusbar and hasattr(self._statusbar_plugin, "add_status_widget"):
            try:
                self._statusbar_plugin.add_status_widget(self._status_bar_widget)
            except Exception:
                new_statusbar.addPermanentWidget(self._status_bar_widget)
        else:
            new_statusbar.addPermanentWidget(self._status_bar_widget)

        self._current_statusbar = new_statusbar

    @on_plugin_available(plugin=Plugins.Preferences)
    def on_preferences_available(self) -> None:
        """Connect when preferences available."""
        preferences = self.get_plugin(Plugins.Preferences)
        preferences.register_plugin_preferences(self)

    @staticmethod
    def check_compatibility():
        """Check plugin compatibility."""
        valid = True
        message = ""  # Note: Remember to use _("") to localize the string
        return valid, message

    def on_close(self, cancellable: bool = True) -> bool:
        """Handle plugin shutdown."""
        widget = self.get_widget()
        if widget is not None:
            try:
                widget.vim_cmd.cleanup()
            except AttributeError:
                pass
            widget.close()
            if running_in_pytest():
                widget.deleteLater()
        QCoreApplication.processEvents()
        return True

    def get_plugin_actions(self):
        """Return plugin actions."""
        return []

    # ------ SpyderPluginMixin API
    def apply_plugin_settings(self, options) -> None:
        """Apply the config settings."""
        self.get_widget().apply_plugin_settings(options)
