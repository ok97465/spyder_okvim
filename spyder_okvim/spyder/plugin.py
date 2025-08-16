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
    REQUIRES = [Plugins.StatusBar, Plugins.Preferences, Plugins.Editor]
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
        self._vim_cmd = vim_cmd

        if vim_cmd.msg_label is not None and vim_cmd.status_label is not None:
            status_bar_widget = StatusBarVimWidget(
                self._main,
                vim_cmd.msg_label,
                vim_cmd.status_label,
                vim_cmd.commandline,
            )

            statusbar = self.get_plugin(Plugins.StatusBar)
            statusbar.add_status_widget(status_bar_widget)
            self.status_bar_widget = status_bar_widget
            self.statusbar = statusbar
        else:
            self.status_bar_widget = None
            self.statusbar = None

        editorsplitter = vim_cmd.editor_widget.get_widget().editorsplitter

        esc_shortcut = QShortcut(
            QKeySequence("Esc"),
            editorsplitter,
            vim_cmd.commandline.setFocus,
        )
        esc_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        if not running_in_pytest():
            self._setup_window_hooks()

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

    # ---- Private helpers -------------------------------------------------
    def _setup_window_hooks(self) -> None:
        """Install hooks to handle undocked and new editor windows."""
        editor = self.get_plugin(Plugins.Editor, error=False)
        if editor is None or not hasattr(editor, "create_window"):
            return

        # Patch editor.create_window for undock action
        orig_create_window = editor.create_window

        def create_window_wrapper(*args, **kwargs):
            res = orig_create_window(*args, **kwargs)
            window = getattr(editor, "_undocked_window", None)
            if window is not None:
                self._add_cmd_to_window(window)
            return res

        editor.create_window = create_window_wrapper

        # Patch editor.close_window to restore status bar command line
        orig_close_window = editor.close_window

        def close_window_wrapper(*args, **kwargs):
            res = orig_close_window(*args, **kwargs)
            self._restore_statusbar_cmd()
            return res

        editor.close_window = close_window_wrapper

        # Patch creation of additional editor windows (New Window)
        main_widget = editor.get_widget()
        orig_new_window = main_widget.create_new_window

        def create_new_window_wrapper(*args, **kwargs):
            window = orig_new_window(*args, **kwargs)
            self._setup_new_editor_window(window)
            return window

        main_widget.create_new_window = create_new_window_wrapper

        self._extra_vim_cmds = []

    def _add_cmd_to_window(self, window) -> None:
        """Move main command line to an undocked editor window."""
        try:
            self.statusbar.remove_status_widget(self.status_bar_widget.ID)
        except Exception:
            pass

        window.statusBar().addPermanentWidget(self._vim_cmd.commandline)

    def _restore_statusbar_cmd(self) -> None:
        """Restore command line to main window status bar."""
        self.status_bar_widget.cmd_line = self._vim_cmd.commandline
        self.status_bar_widget.set_layout()
        try:
            self.statusbar.add_status_widget(self.status_bar_widget)
        except Exception:
            pass

    def _setup_new_editor_window(self, window) -> None:
        """Create a command line for a new editor window."""
        vim_cmd = VimWidget(self._vim_cmd.editor_widget, self._main, with_labels=False)
        window.statusBar().addPermanentWidget(vim_cmd.commandline)
        shortcut = QShortcut(
            QKeySequence("Esc"),
            window.editorwidget.editorsplitter,
            vim_cmd.commandline.setFocus,
        )
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._extra_vim_cmds.append((vim_cmd, shortcut))
