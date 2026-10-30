# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) Spyder Project Contributors
#
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
# -----------------------------------------------------------------------------
"""OkVim Plugin."""

# Standard Libraries
import weakref

# Third Party Libraries
import qtawesome as qta
from qtpy.QtCore import QCoreApplication, QEvent, Qt, Signal
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import QHBoxLayout, QMainWindow, QShortcut
from spyder.api.plugin_registration.decorators import (
    on_plugin_available,
    on_plugin_teardown,
)
from spyder.api.plugins import Plugins, SpyderDockablePlugin

# Project Libraries
from spyder_okvim.utils.testing_env import running_in_pytest
from spyder.api.widgets.status import StatusBarWidget
from spyder.utils.icon_manager import MAIN_FG_COLOR

# Project Libraries
from spyder_okvim.spyder.api import CustomLayout
from spyder_okvim.spyder.config import CONF_DEFAULTS, CONF_SECTION, CONF_VERSION
from spyder_okvim.spyder.confpage import OkvimConfigPage
from spyder_okvim.spyder.switcher import SwitcherNavigation
from spyder_okvim.spyder.vim_widgets import VimPane
from spyder_okvim.utils.qtcompat import live_widget, widget_is_deleted


class StatusBarVimWidget(StatusBarWidget):
    """Status bar widget for okvim."""

    ID = f"{CONF_SECTION}_status_bar"
    CONF_SECTION = CONF_SECTION  # Ensure Qt mixins see the configuration section

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
    REQUIRES = [
        Plugins.StatusBar,
        Plugins.Preferences,
        Plugins.Application,
        Plugins.Editor,
    ]
    OPTIONAL = [Plugins.Switcher]
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
        self._status_bar_widget = status_bar_widget
        self._main_statusbar = status_bar_widget.parentWidget()

        self._editor_widget = vim_cmd.editor_widget.get_widget()
        self._active_stack = None
        self._active_editor = None
        self._status_window = None
        self._window_stacks = weakref.WeakKeyDictionary()
        self._vim_focus = weakref.WeakKeyDictionary()
        self._editors = weakref.WeakSet()
        self._closing_windows = weakref.WeakSet()
        self._switcher_navigation = SwitcherNavigation(self)
        vim_cmd.commandline.installEventFilter(self)
        self._editor_widget.installEventFilter(self)
        signal = getattr(self._editor_widget, "sig_editor_focus_changed", None)
        if signal is not None:
            signal.connect(self._on_editor_focus_changed)
        self._on_editor_focus_changed()
        self._sync_statusbar()

    def eventFilter(self, watched, event):
        """Track the active editor view and rescue shared UI before it closes."""
        if event.type() == QEvent.FocusIn:
            if watched is self.vim_cmd.commandline:
                self._vim_focus[watched.window()] = True
            elif (
                watched in self._editors
                and event.reason() != Qt.ActiveWindowFocusReason
            ):
                self._vim_focus[watched.window()] = False
        if event.type() == QEvent.WindowActivate and watched in self._window_stacks:
            stack = live_widget(self._window_stacks[watched])
            if stack is not None and watched not in self._closing_windows:
                self._use_stack(stack)
                if self._vim_focus.get(watched, False):
                    self.vim_cmd.commandline.setFocus()
        if event.type() == QEvent.Close and watched in self._window_stacks:
            if watched is not self._main:
                self._closing_windows.add(watched)
        if event.type() == QEvent.Close and (
            watched is live_widget(self._status_window)
            or watched is live_widget(self._active_stack)
        ):
            if watched is not self._main and isinstance(watched, QMainWindow):
                self._closing_windows.add(watched)
            self._reset_view()
            self._active_stack = None
            self._active_editor = None
            self.vim_cmd.vim_status.cursor.set_editorstack(None)
            self._move_statusbar(self._main_statusbar)
            self._move_labels(self._editor_widget)
        if watched is self._editor_widget and event.type() in (
            QEvent.ParentChange,
            QEvent.Show,
        ):
            self._sync_statusbar()
        return super().eventFilter(watched, event)

    def _on_editor_focus_changed(self):
        """Discover new windows/splits through Spyder's editor focus signal."""
        stack = self.vim_cmd.editor_widget.get_current_editorstack()
        self._use_stack(stack)

    def _use_stack(self, stack):
        """Bind both Vim and Spyder commands to the selected editor view."""
        if stack is None or stack.window() in self._closing_windows:
            return
        editor = stack.get_current_editor()
        if editor is not live_widget(self._active_editor):
            self._reset_view()
        self._active_stack = weakref.ref(stack)
        self._active_editor = weakref.ref(editor) if editor is not None else None
        self.vim_cmd.vim_status.cursor.set_editorstack(stack)
        self.vim_cmd.which_key.set_editor(editor)
        self.vim_cmd.substitute_preview.set_editor(editor)
        self.vim_cmd.commandline_popup.set_editor(editor)
        self.vim_cmd.put_controller.bind_editor(editor)
        if editor is not None and editor not in self._editors:
            self._editors.add(editor)
            editor.installEventFilter(self)
            self._vim_focus[stack.window()] = False
        save_stack = getattr(self._editor_widget, "set_last_focused_editorstack", None)
        if save_stack is not None:
            owner = (
                self._editor_widget
                if self._editor_widget.isAncestorOf(stack)
                else stack.window()
            )
            save_stack(owner, stack)
        shortcut = stack.findChild(QShortcut, "okvim_escape", Qt.FindDirectChildrenOnly)
        if shortcut is None:
            shortcut = QShortcut(QKeySequence("Esc"), stack, self._focus_vim)
            shortcut.setObjectName("okvim_escape")
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            stack.installEventFilter(self)
        self._sync_statusbar()
        self.vim_cmd.vim_status.search.refresh()

    def _focus_vim(self):
        """Keep the command line and command target on the focused stack."""
        self._use_stack(self.sender().parent())
        self.vim_cmd.commandline.setFocus()

    def _reset_view(self):
        """Cancel partial commands before they can cross into another view."""
        self.vim_cmd.substitute_preview.set_editor(None)
        self.vim_cmd.which_key.cancel()
        self.vim_cmd.which_key.set_editor(None)
        self.vim_cmd.commandline_popup.set_editor(None)
        self.vim_cmd.cancel_yank_picker()
        self.vim_cmd.put_controller.bind_editor(None)
        status = self.vim_cmd.vim_status
        self.vim_cmd.cancel_macro()
        if status.is_recording_macro():
            status.stop_recording_macro()
        status.finish_insert(apply_count=False)
        status.disconnect_from_editor()
        editor = live_widget(self._active_editor)
        if editor is not None:
            editor.clear_extra_selections("vim_selection")
            editor.clear_extra_selections("vim_cursor")
        if status.sub_mode is not None:
            status.sub_mode.on_escape()
        status.sub_mode = None
        status.input_cmd.clear()
        status.clear_state()
        status.set_message("")
        self.vim_cmd.commandline.clear()
        self.vim_cmd.commandline.sync_input_method()

    def _move_labels(self, parent):
        """Keep shared Leap labels under a live ancestor of the active view."""
        for label in self.vim_cmd.vim_status.labels_for_annotate:
            if label.parentWidget() is not parent:
                label.hide()
                label.setParent(parent)

    def _move_statusbar(self, statusbar):
        """Reparent the same status widget without changing its registration."""
        widget = self._status_bar_widget
        if widget.parentWidget() is not statusbar:
            widget.parentWidget().removeWidget(widget)
            statusbar.insertPermanentWidget(0, widget)
            widget.show()

    def _sync_statusbar(self):
        """Move the existing Vim UI without recreating widgets or shortcuts."""
        stack = live_widget(self._active_stack)
        window = stack.window() if stack is not None else self._editor_widget.window()
        if window is self._main:
            statusbar = self._main_statusbar
            label_parent = self._editor_widget
        elif isinstance(window, QMainWindow):
            statusbar = window.statusBar()
            label_parent = window.centralWidget()
        else:
            # Qt can temporarily leave the pane without its final parent.
            return
        if window not in self._window_stacks:
            window.installEventFilter(self)
        self._window_stacks[window] = weakref.ref(stack) if stack is not None else None
        self._status_window = weakref.ref(window)
        self._move_statusbar(statusbar)
        self._move_labels(label_parent)

    @on_plugin_available(plugin=Plugins.Preferences)
    def on_preferences_available(self) -> None:
        """Connect when preferences available."""
        preferences = self.get_plugin(Plugins.Preferences)
        preferences.register_plugin_preferences(self)

    @on_plugin_available(plugin=Plugins.Switcher)
    def on_switcher_available(self) -> None:
        """Add Vim navigation to Spyder's shared file and symbol switcher."""
        switcher = self.get_plugin(Plugins.Switcher).get_container().switcher
        self._switcher_navigation.attach(switcher)

    @on_plugin_teardown(plugin=Plugins.Switcher)
    def on_switcher_teardown(self) -> None:
        """Remove navigation when the switcher or OkVim is disabled."""
        navigation = getattr(self, "_switcher_navigation", None)
        if navigation is not None:
            navigation.detach()

    @staticmethod
    def check_compatibility():
        """Check plugin compatibility."""
        valid = True
        message = ""  # Note: Remember to use _("") to localize the string
        return valid, message

    def on_close(self, cancellable: bool = True) -> bool:
        """Handle plugin shutdown."""
        self.on_switcher_teardown()
        if hasattr(self, "_editor_widget"):
            self._editor_widget.removeEventFilter(self)
            self.vim_cmd.commandline.removeEventFilter(self)
            for editor in self._editors:
                if not widget_is_deleted(editor):
                    editor.removeEventFilter(self)
            signal = getattr(self._editor_widget, "sig_editor_focus_changed", None)
            if signal is not None:
                signal.disconnect(self._on_editor_focus_changed)
            for window in self._window_stacks:
                if not widget_is_deleted(window):
                    window.removeEventFilter(self)
            stacks = getattr(self._editor_widget, "editorstacks", None)
            if stacks is None:
                stacks = [self.vim_cmd.editor_widget.get_current_editorstack()]
            for stack in stacks:
                if not widget_is_deleted(stack):
                    stack.removeEventFilter(self)
                    shortcut = stack.findChild(
                        QShortcut, "okvim_escape", Qt.FindDirectChildrenOnly
                    )
                    if shortcut is not None:
                        shortcut.setEnabled(False)
                        shortcut.deleteLater()
            # The detached Editor window must not own the command input when
            # it is deleted after the plugin has stopped tracking reparenting.
            self._move_statusbar(self._main_statusbar)
            self._move_labels(self._editor_widget)
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
