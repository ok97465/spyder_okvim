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

        # Status widget to display vim information and accept commands
        self._status_widget = StatusBarVimWidget(
            self._main,
            vim_cmd.msg_label,
            vim_cmd.status_label,
            vim_cmd.commandline,
        )

        # Keep reference to StatusBar plugin and the underlying QStatusBar
        self._statusbar = self.get_plugin(Plugins.StatusBar)
        self._statusbar.add_status_widget(self._status_widget)
        self._main_statusbar = getattr(self._statusbar, "_statusbar", None)
        self._statusbar_parent = self._main_statusbar

        # Keep track of Esc shortcuts created for each editor window
        self._esc_shortcuts = {}
        self._current_window = None

        # React to focus changes in the editor to support undocked windows
        editor_plugin = vim_cmd.editor_widget
        if hasattr(editor_plugin, "sig_editor_focus_changed"):
            editor_plugin.sig_editor_focus_changed.connect(
                self._on_editor_focus_changed
            )

        # Ensure we install things for the main window
        self._setup_editor_window(self._main)

    @on_plugin_available(plugin=Plugins.Preferences)
    def on_preferences_available(self) -> None:
        """Connect when preferences available."""
        preferences = self.get_plugin(Plugins.Preferences)
        preferences.register_plugin_preferences(self)

    # ---- Private API -------------------------------------------------
    def _get_editorsplitter(self, window):
        """Return the editorsplitter for a given editor window."""
        if window is self._main:
            return self.vim_cmd.editor_widget.get_widget().editorsplitter
        if hasattr(window, "editorwidget"):
            return window.editorwidget.editorsplitter
        central = window.centralWidget()
        return getattr(central, "editorsplitter", None)

    def _setup_editor_window(self, window):
        """Install shortcuts and status bar widget for *window*."""
        if window is None:
            return

        # Install Esc shortcut if not created yet
        if window not in self._esc_shortcuts:
            editorsplitter = self._get_editorsplitter(window)
            if editorsplitter is not None:
                esc_shortcut = QShortcut(
                    QKeySequence("Esc"),
                    editorsplitter,
                    self.vim_cmd.commandline.setFocus,
                )
                esc_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
                self._esc_shortcuts[window] = esc_shortcut

        # Move status widget to the window's status bar if needed
        if hasattr(window, "statusBar"):
            statusbar = window.statusBar()
            if statusbar is not self._statusbar_parent:
                if (
                    self._statusbar_parent is self._main_statusbar
                    and self._main_statusbar is not None
                ):
                    self._statusbar.remove_status_widget(self._status_widget.ID)
                elif self._statusbar_parent is not None:
                    try:
                        self._statusbar_parent.removeWidget(self._status_widget)
                    except Exception:
                        pass

                if statusbar is self._main_statusbar and self._main_statusbar is not None:
                    self._statusbar.add_status_widget(self._status_widget)
                else:
                    statusbar.addPermanentWidget(self._status_widget)

                self._statusbar_parent = statusbar

        self._current_window = window

    def _on_editor_focus_changed(self):
        """Handle focus changes to update shortcuts and status widget."""
        editor_plugin = self.vim_cmd.editor_widget
        editorstack = editor_plugin.get_current_editorstack()
        if editorstack is None:
            return
        window = editorstack.window()
        self._setup_editor_window(window)

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
