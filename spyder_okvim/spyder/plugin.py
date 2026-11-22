# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) Spyder Project Contributors
#
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
# -----------------------------------------------------------------------------
"""Route Spyder editor views and shared Vim UI through the plugin lifecycle.

The plugin binds the active stack, reparents status widgets between windows and
cancels old view work before a replacement is selected. Split-close focus intent
belongs to this transition; delayed input delivery remains editor-bound.
"""

# Standard Libraries
import weakref

# Third Party Libraries
import qtawesome as qta
from qtpy.QtCore import QCoreApplication, QEvent, QObject, QSize, Qt, QTimer, Signal
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QShortcut,
    QSizePolicy,
    QWidget,
)
from spyder.api.fonts import SpyderFontType
from spyder.api.plugin_registration.decorators import (
    on_plugin_available,
    on_plugin_teardown,
)
from spyder.api.plugins import Plugins, SpyderDockablePlugin
from spyder.api.widgets.status import StatusBarWidget
from spyder.utils.icon_manager import ima

# Project Libraries
from spyder_okvim.spyder.api import CustomLayout
from spyder_okvim.spyder.config import CONF_DEFAULTS, CONF_SECTION, CONF_VERSION
from spyder_okvim.spyder.confpage import OkvimConfigPage
from spyder_okvim.spyder.switcher import SwitcherNavigation
from spyder_okvim.spyder.vim_widgets import VimPane
from spyder_okvim.utils.editor_windows import remember_pane
from spyder_okvim.utils.qtcompat import live_widget, widget_is_deleted
from spyder_okvim.utils.testing_env import running_in_pytest


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
        self._preferred_width = 0
        self._observed_parent = None
        self._parent_observer_ready = False
        super().__init__(parent, show_icon=False, show_label=False)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.cmd_line.setAccessibleName("Vim command input")
        self.cmd_line.setAccessibleDescription("Enter Vim commands, searches or keys")
        self.cmd_line.installEventFilter(self)
        self._parent_observer_ready = True
        self._observe_parent()
        self._update_space()

    # ---- Private API -------------------------------------------------
    def _set_layout(self):
        """Create the internal layout of the status bar widget."""
        layout = QHBoxLayout(self)
        layout.setSpacing(5)
        self.msg_label.setMinimumWidth(0)
        self.cmd_line.setMinimumWidth(0)
        self.cmd_line.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout.addWidget(self.msg_label, 3)
        layout.addWidget(self.status_label)
        layout.addWidget(self.cmd_line, 2)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def _update_space(self):
        """Fit the status bar to its host without resizing it during input."""
        if widget_is_deleted(self.cmd_line):
            return
        parent = self.parentWidget()
        available = parent.width() if parent is not None else self.window().width()
        # Leave room for the host's other status widgets. Font metrics keep
        # these preferred widths proportional to the current display scale.
        character_width = self.cmd_line.fontMetrics().horizontalAdvance("M")
        desired = character_width * 48
        limit = max(1, round(available * 0.65))
        self._preferred_width = min(desired, limit)
        self.setMaximumWidth(limit)
        self.updateGeometry()

    def sizeHint(self):
        hint = super().sizeHint()
        return QSize(self._preferred_width or hint.width(), hint.height())

    def _observe_parent(self):
        """Follow the actual status bar, including Spyder's first insertion."""
        parent = self.parentWidget()
        previous = live_widget(self._observed_parent)
        if previous is parent:
            return
        if previous is not None:
            previous.removeEventFilter(self)
        self._observed_parent = weakref.ref(parent) if parent is not None else None
        if parent is not None:
            parent.installEventFilter(self)

    def event(self, event):
        result = super().event(event)
        if event.type() == QEvent.ParentChange and self._parent_observer_ready:
            self._observe_parent()
            self._update_space()
        return result

    def eventFilter(self, watched, event):
        if event.type() in (
            QEvent.Resize,
            QEvent.FontChange,
            QEvent.ParentChange,
            QEvent.Show,
        ):
            self._update_space()
        return super().eventFilter(watched, event)


class _VimFocusGuard(QObject):
    """Track Qt's automatic focus and newer clicks while input is queued."""

    automatic_focus = None
    clicked = False

    def start(self):
        self.automatic_focus = None
        self.clicked = False
        QApplication.instance().installEventFilter(self)

    def stop(self):
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self.automatic_focus = None
        self.clicked = False

    def eventFilter(self, watched, event):
        if event.type() == QEvent.MouseButtonPress:
            self.clicked = True
        elif event.type() == QEvent.FocusIn and isinstance(watched, QWidget):
            self.automatic_focus = (
                weakref.ref(watched)
                if event.reason() == Qt.ActiveWindowFocusReason
                else None
            )
        return False


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
    CONF_VERSION = CONF_VERSION
    CUSTOM_LAYOUTS = [CustomLayout]
    CAN_BE_DISABLED = True
    RAISE_AND_FOCUS = True

    @property
    def vim_cmd(self):
        """Return the shared command widget owned by the plugin pane."""
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
        return qta.icon("mdi.vimeo", color=ima.MAIN_FG_COLOR)

    def on_initialize(self) -> None:
        """Perform plugin initialization after it is added to Spyder."""
        vim_cmd = self.get_widget().vim_cmd
        self.update_font()

        status_bar_widget = StatusBarVimWidget(
            self._main,
            vim_cmd.msg_label,
            vim_cmd.status_label,
            vim_cmd.commandline,
        )

        statusbar = self.get_plugin(Plugins.StatusBar)
        statusbar.add_status_widget(status_bar_widget)
        self._status_bar_widget = status_bar_widget
        self._statusbar_attached = True
        self._main_statusbar = status_bar_widget.parentWidget()

        self._editor_widget = vim_cmd.editor_widget.get_widget()
        self._active_stack = None
        self._active_editor = None
        self._input_focus_after_split_close = None
        self._status_window = None
        self._activated_window = None
        self._requested_vim_focus = None
        self._focus_guard = _VimFocusGuard(self)
        self._host_update_timer = QTimer(self)
        self._host_update_timer.setSingleShot(True)
        self._host_update_timer.timeout.connect(self._update_host)
        self._window_stacks = weakref.WeakKeyDictionary()
        self._vim_focus = weakref.WeakKeyDictionary()
        self._editors = weakref.WeakSet()
        self._closing_windows = weakref.WeakSet()
        self._switcher_navigation = SwitcherNavigation(self)
        vim_cmd.commandline.installEventFilter(self)
        self._editor_widget.installEventFilter(self)
        self._editor_connections = []
        for name, callback in (
            ("sig_editor_focus_changed", self._on_editor_focus_changed),
            ("sig_codeeditor_deleted", self._on_editor_deleted),
        ):
            signal = getattr(self._editor_widget, name, None)
            if signal is not None:
                signal.connect(callback)
                self._editor_connections.append((signal, callback))
        self._use_stack(vim_cmd.editor_widget.get_current_editorstack())
        if self._active_stack is None:
            self._sync_statusbar()

    def eventFilter(self, watched, event):
        """Track the active editor view and rescue shared UI before it closes."""
        event_type = event.type()
        if event_type == QEvent.FocusIn:
            if watched is self.vim_cmd.commandline:
                self._vim_focus[watched.window()] = True
            elif (
                watched in self._editors
                and event.reason() != Qt.ActiveWindowFocusReason
            ):
                self._vim_focus[watched.window()] = False
        if (
            event_type == QEvent.WindowActivate
            and self._statusbar_attached
            and watched in self._window_stacks
        ):
            self._activated_window = weakref.ref(watched)
            self._focus_guard.start()
            self._queue_host_update()
        if event_type == QEvent.Close and watched in self._window_stacks:
            if watched is not self._main:
                self._closing_windows.add(watched)
            self._input_focus_after_split_close = None
        if event_type == QEvent.Close and (
            watched is live_widget(self._status_window)
            or watched is live_widget(self._active_stack)
        ):
            if (
                watched is live_widget(self._active_stack)
                and self.vim_cmd.commandline.hasFocus()
            ):
                # Closing a Vim-focused split hands input to its replacement.
                # The request belongs to the host transition, not the deleted
                # editor, and is scheduled only after the new view is bound.
                self._input_focus_after_split_close = weakref.ref(watched.window())
            if watched is not self._main and isinstance(watched, QMainWindow):
                self._closing_windows.add(watched)
            self._reset_view()
            self._active_stack = None
            self._active_editor = None
            self.vim_cmd.vim_status.cursor.set_editorstack(None)
            self._move_statusbar(self._main_statusbar)
            self._move_labels(self._editor_widget)
        if watched is self._editor_widget and event_type in (
            QEvent.ParentChange,
            QEvent.Show,
        ):
            self._queue_host_update()
        return super().eventFilter(watched, event)

    def _queue_host_update(self):
        """Wait for Qt to finish sending focus and docking notifications."""
        if self._statusbar_attached and not self._host_update_timer.isActive():
            self._host_update_timer.start(0)

    def _cancel_host_update(self):
        self._host_update_timer.stop()
        self._activated_window = None
        self._requested_vim_focus = None
        self._focus_guard.stop()

    def request_vim_focus(self, editor) -> None:
        """Restore Vim input for an explicitly selected editor after docking."""
        if (
            self._statusbar_attached
            and editor is not None
            and not widget_is_deleted(editor)
        ):
            self._requested_vim_focus = weakref.ref(editor)
            self._focus_guard.start()
            self._queue_host_update()

    def _update_host(self):
        """Apply the latest host change and restore focus for a live activation."""
        activated_window = live_widget(self._activated_window)
        requested_editor = live_widget(self._requested_vim_focus)
        automatic_focus = live_widget(self._focus_guard.automatic_focus)
        clicked = self._focus_guard.clicked
        self._cancel_host_update()
        if not self._statusbar_attached:
            return
        window = QApplication.activeWindow()
        stack = None
        if (
            window is not None
            and window is activated_window
            and window not in self._closing_windows
        ):
            stack = live_widget(self._window_stacks.get(window))
        if stack is not None and stack.window() is window and stack.isVisible():
            self._use_stack(stack)
            if clicked and QApplication.focusWidget() is not self.vim_cmd.commandline:
                self._vim_focus[window] = False
            restore_focus = self._vim_focus.get(window, False)
        else:
            self._sync_statusbar()
            restore_focus = False
        restore_requested = (
            requested_editor is not None
            and requested_editor is live_widget(self._active_editor)
        )
        if not clicked and (restore_focus or restore_requested):
            self._restore_window_focus(
                window, automatic_focus=automatic_focus if restore_focus else None
            )

    def _restore_window_focus(self, window, *, automatic_focus):
        """Restore the remembered Vim focus after Qt has chosen an active view."""
        if window is self._main and not getattr(
            self._editor_widget, "is_visible", True
        ):
            return
        commandline = self.vim_cmd.commandline
        editor = live_widget(self._active_editor)
        focus = QApplication.focusWidget()
        if (
            window is not None
            and window is QApplication.activeWindow()
            and window not in self._closing_windows
            and editor is not None
            and editor.isVisible()
            and editor.window() is window
            and not widget_is_deleted(commandline)
            and commandline.isVisible()
            and commandline.window() is window
            and (
                focus is None
                or focus is commandline
                or focus is editor
                or (focus is automatic_focus and focus.window() is window)
            )
        ):
            commandline.setFocus()

    def _on_editor_focus_changed(self):
        """Discover new windows/splits through Spyder's editor focus signal."""
        stack = self.vim_cmd.editor_widget.get_current_editorstack()
        self._use_stack(stack, sync_host=False)

    def _on_editor_deleted(self, editor):
        """Release view work even if closing the last tab produces no focus event."""
        reference = self._active_editor
        active_editor = live_widget(reference)
        stack = live_widget(self._active_stack)
        # Spyder closes sibling clones with their signals blocked. The active
        # view can disappear even when the deletion signal names another view.
        if reference is not None and (
            active_editor is None
            or editor is active_editor
            or (stack is not None and stack.get_current_editor() is not active_editor)
        ):
            self._reset_view(preserve_definition=True)
            if reference is self._active_editor:
                self._active_editor = None
        self.vim_cmd.vim_status.search.release_closed_editor(editor)

    def _use_stack(self, stack, *, sync_host=True):
        """Bind commands to a view before restoring a closed split's Vim focus.

        A pending close handoff is valid only in its original host window.
        View-bound work is cancelled before the new input-focus request is
        scheduled. Definition tracking spans the switch to observe gd's arrival.
        """
        if stack is None or widget_is_deleted(stack):
            return
        window = stack.window()
        if window in self._closing_windows:
            return
        restore_input = live_widget(self._input_focus_after_split_close) is window
        self._input_focus_after_split_close = None
        editor = stack.get_current_editor()
        if editor is not None and widget_is_deleted(editor):
            editor = None
        changed_editor = editor is not live_widget(self._active_editor)
        if changed_editor and not self.vim_cmd.picker.allows_navigation(stack):
            # Definition navigation switches editors before placing the cursor.
            # Keep its arrival watch alive through the destination's binding.
            self._reset_view(preserve_definition=True)
        self._active_stack = weakref.ref(stack)
        self._active_editor = weakref.ref(editor) if editor is not None else None
        if window in self._window_stacks:
            self._window_stacks[window] = self._active_stack
        remember_pane(self.vim_cmd.vim_status, stack)
        self.vim_cmd.vim_status.cursor.set_editorstack(stack)
        self.vim_cmd.bind_editor(editor)
        if editor is not None and editor not in self._editors:
            self._editors.add(editor)
            editor.installEventFilter(self)
            self._vim_focus[window] = False
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
        if sync_host:
            self._sync_statusbar()
        else:
            self._queue_host_update()
        self.vim_cmd.vim_status.search.refresh()
        if restore_input:
            self.vim_cmd.vim_status.set_focus_to_vim_after_delay(0)

    def _focus_vim(self):
        """Keep the command line and command target on the focused stack."""
        self._use_stack(self.sender().parent())
        self.vim_cmd.commandline.setFocus()

    def _reset_view(self, *, preserve_definition=False):
        """Cancel partial commands before they can cross into another view."""
        reference = self._active_editor
        vim_cmd = self.vim_cmd
        vim_cmd.bind_editor(None)
        status = vim_cmd.vim_status
        if status.is_recording_macro():
            status.stop_recording_macro()
        status.cancel_pending_work(preserve_definition=preserve_definition)
        if status.sub_mode is not None:
            status.sub_mode.on_escape()
        status.sub_mode = None
        status.input_cmd.clear()
        status.clear_state(previous_editor=live_widget(reference))
        status.set_message("")
        vim_cmd.commandline.clear()
        vim_cmd.commandline.sync_input_method()

    def _move_labels(self, parent):
        """Keep shared Leap labels under a live ancestor of the active view."""
        if parent is None or widget_is_deleted(parent):
            return
        for label in self.vim_cmd.vim_status.labels_for_annotate:
            if not widget_is_deleted(label) and label.parentWidget() is not parent:
                label.hide()
                label.setParent(parent)

    def _move_statusbar(self, statusbar):
        """Reparent the same status widget without changing its registration."""
        if (
            not self._statusbar_attached
            or statusbar is None
            or widget_is_deleted(statusbar)
        ):
            return
        widget = self._status_bar_widget
        if widget_is_deleted(widget):
            return
        parent = widget.parentWidget()
        if parent is not statusbar:
            if parent is not None:
                parent.removeWidget(widget)
            statusbar.insertPermanentWidget(0, widget)
            widget._update_space()
            widget.show()

    def _sync_statusbar(self):
        """Move the existing Vim UI without recreating widgets or shortcuts."""
        if not self._statusbar_attached or widget_is_deleted(self._editor_widget):
            return
        stack = live_widget(self._active_stack)
        window = stack.window() if stack is not None else self._editor_widget.window()
        if window in self._closing_windows:
            return
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

    @on_plugin_teardown(plugin=Plugins.Preferences)
    def on_preferences_teardown(self) -> None:
        """Remove the preference page when this plugin or Preferences stops."""
        preferences = self.get_plugin(Plugins.Preferences)
        preferences.deregister_plugin_preferences(self)

    @on_plugin_teardown(plugin=Plugins.StatusBar)
    def on_statusbar_teardown(self) -> None:
        """Release the status ID so disabling and re-enabling OkVim is safe."""
        if getattr(self, "_statusbar_attached", False):
            self._cancel_host_update()
            self._move_statusbar(self._main_statusbar)
            statusbar = self.get_plugin(Plugins.StatusBar)
            statusbar.remove_status_widget(StatusBarVimWidget.ID)
            self._status_bar_widget.hide()
            self._statusbar_attached = False

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

    def update_font(self) -> None:
        """Follow Spyder's editor font for commands and their popup contents."""
        widget = self.get_widget()
        if widget is not None:
            widget.vim_cmd.commandline.setFont(self.get_font(SpyderFontType.Monospace))

    def on_close(self, cancellable: bool = True) -> bool:
        """Handle plugin shutdown."""
        self._input_focus_after_split_close = None
        self.on_switcher_teardown()
        if hasattr(self, "_editor_widget"):
            self._cancel_host_update()
            self._editor_widget.removeEventFilter(self)
            self.vim_cmd.commandline.removeEventFilter(self)
            for editor in self._editors:
                if not widget_is_deleted(editor):
                    editor.removeEventFilter(self)
            for signal, callback in self._editor_connections:
                signal.disconnect(callback)
            self._editor_connections.clear()
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
        self.on_statusbar_teardown()
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
