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
from qtpy.QtWidgets import QHBoxLayout, QShortcut
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
    OPTIONAL = []
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

        statusbar = self.get_plugin(Plugins.StatusBar)
        statusbar.add_status_widget(status_bar_widget)

        editorsplitter = vim_cmd.editor_widget.get_widget().editorsplitter

        self.esc_shortcut = QShortcut(QKeySequence("Esc"), editorsplitter)
        self.esc_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.esc_shortcut.activated.connect(vim_cmd.commandline.setFocus)

        # Keep reference to editor plugin for later use
        self._editor_plugin = vim_cmd.editor_widget
        self._window_vims = {}
        self._floating_vim = None

        # Handle undocking of the main editor pane if possible
        if hasattr(self._editor_plugin, "dockwidget"):
            dock = self._editor_plugin.dockwidget
            dock.topLevelChanged.connect(self._on_editor_floating)

        # Setup Vim widgets for additional editor windows
        editor_widget = self._editor_plugin.get_widget()
        if hasattr(editor_widget, "register_editorwindow"):
            original_register = editor_widget.register_editorwindow

            def register_editorwindow(window):
                original_register(window)
                self._add_window_vim(window)

            editor_widget.register_editorwindow = register_editorwindow
            for win in getattr(editor_widget, "editorwindows", []):
                self._add_window_vim(win)

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
        for vim, shortcut in getattr(self, "_window_vims", {}).values():
            vim.cleanup()
            if running_in_pytest():
                vim.commandline.deleteLater()
            shortcut.setParent(None)
        self._window_vims = {}
        if getattr(self, "_floating_vim", None) is not None:
            self._floating_vim.cleanup()
            if running_in_pytest():
                self._floating_vim.commandline.deleteLater()
            self._floating_vim = None
        QCoreApplication.processEvents()
        return True

    def get_plugin_actions(self):
        """Return plugin actions."""
        return []

    # ------ SpyderPluginMixin API
    def apply_plugin_settings(self, options) -> None:
        """Apply the config settings."""
        self.get_widget().apply_plugin_settings(options)

    # ---- Internal helpers -------------------------------------------------
    def _add_window_vim(self, window) -> None:
        """Create a Vim command line for a new editor window."""
        if window in self._window_vims:
            return
        vim = VimWidget(self._editor_plugin, self._main, editor_window=window, minimal=True)
        editor_widgets = window.editorwidget.editorsplitter.parent()
        editor_widgets.layout().addWidget(vim.commandline)
        shortcut = QShortcut(QKeySequence("Esc"), window.editorwidget.editorsplitter)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.activated.connect(vim.commandline.setFocus)
        self._window_vims[window] = (vim, shortcut)

    def _on_editor_floating(self, floating: bool) -> None:
        """Handle undocking/docking of the main editor pane."""
        if floating:
            if self._floating_vim is None:
                self._floating_vim = VimWidget(
                    self._editor_plugin, self._main, minimal=True
                )
                editor_widget = self._editor_plugin.get_widget()
                editor_widget.layout().addWidget(self._floating_vim.commandline)
            try:
                self.esc_shortcut.activated.disconnect()
            except Exception:
                pass
            self.esc_shortcut.activated.connect(
                self._floating_vim.commandline.setFocus
            )
        else:
            if self._floating_vim is not None:
                self._floating_vim.commandline.setParent(None)
                self._floating_vim.cleanup()
                if running_in_pytest():
                    self._floating_vim.commandline.deleteLater()
                self._floating_vim = None
            try:
                self.esc_shortcut.activated.disconnect()
            except Exception:
                pass
            self.esc_shortcut.activated.connect(
                self.get_widget().vim_cmd.commandline.setFocus
            )
