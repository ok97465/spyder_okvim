# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) Spyder Project Contributors
#
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
# -----------------------------------------------------------------------------
"""OkVim Widget."""

# Standard Libraries
import os
import os.path as osp
import re
import sys
import threading
import weakref
from contextlib import contextmanager
from functools import wraps

# Third Party Libraries
from qtpy.QtCore import QEvent, QObject, Qt, QThread, Signal, Slot
from qtpy.QtGui import (
    QFocusEvent,
    QInputMethodEvent,
    QKeyEvent,
    QKeySequence,
    QTextCursor,
)
from qtpy.QtWidgets import QApplication, QHBoxLayout, QLabel, QLineEdit, QWidget, QStyle
from spyder.api.config.decorators import on_conf_change
from spyder.api.plugins import Plugins
from spyder.api.widgets.main_widget import PluginMainWidget
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.executor import (
    ExecutorLeaderKey,
    ExecutorNormalCmd,
    ExecutorVisualCmd,
    ExecutorVlineCmd,
)
from spyder_okvim.executor.executor_sub import ExecutorSubCmd_window
from spyder_okvim.spyder.commandline_popup_controller import (
    CommandlinePopupController,
)
from spyder_okvim.spyder.config import CONF_SECTION, KEYCODE2STR
from spyder_okvim.spyder.substitute_preview import SubstitutePreviewController
from spyder_okvim.spyder.which_key import PendingHint, WhichKeyController
from spyder_okvim.utils.commandline import completion_candidates
from spyder_okvim.utils.ex_parser import ExError, is_substitute, scan_header
from spyder_okvim.utils.file_search import FileSearchDialog
from spyder_okvim.utils.key_helpers import latin_command_key
from spyder_okvim.utils.put import PutController
from spyder_okvim.utils.qtcompat import exec_dialog, text_width, widget_is_deleted
from spyder_okvim.utils.testing_env import running_in_pytest
from spyder_okvim.utils.yank_dialog import YankHistoryPicker
from spyder_okvim.vim import InputCmdInfo, KeyInfo, VimState, VimStatus

running_coverage = "coverage" in sys.modules


def enable_coverage_tracing(fn):
    """Apply coverage tracing to a thread entry point."""

    @wraps(fn)
    def wrapped(*args, **kwargs):
        if running_coverage:
            sys.settrace(threading._trace_hook)
        fn(*args, **kwargs)

    return wrapped


class VimPane(PluginMainWidget):
    """Invisible pane used to host the Vim command widget."""

    def __init__(self, name=None, plugin=None, parent=None):
        """Create the pane and its underlying Vim widget."""
        super().__init__(name, plugin, parent)
        layout = QHBoxLayout()
        layout.addWidget(QLabel("Please hide this pane."))
        self.setLayout(layout)

        self.main = parent
        self.vim_cmd = VimWidget(self.main.editor, self.main)

    def get_title(self):
        """Return the localized title for the pane."""
        return "Okvim"

    def get_focus_widget(self):
        """Return the widget that should receive focus."""
        return self.vim_cmd

    def setup(self):
        """Perform initial setup after the plugin is created."""
        pass

    def update_actions(self):
        """Update actions exposed by the plugin."""
        pass

    @on_conf_change
    def apply_plugin_settings(self, options):
        """Apply the config settings."""
        self.vim_cmd.vim_status.search.set_color()
        self.vim_cmd.apply_settings()


class VimShortcut(QObject):
    """Method class for vim shortcut."""

    signal_cmd = Signal(str)

    def __init__(self, main, vim_status: VimStatus):
        super().__init__()
        self.main = main
        self.vim_status = vim_status
        self.get_editor = self.vim_status.get_editor
        self.cmd_line = None
        self.executor_window = ExecutorSubCmd_window(vim_status)

    def _scroll(self, half: bool, up: bool) -> None:
        """Scroll the editor window.

        Args:
            half: If ``True`` scroll half the visible lines.
            up: Scroll up when ``True`` otherwise scroll down.
        """
        lines = self.vim_status.get_number_of_visible_lines()
        if half:
            lines //= 2
        if lines < 1:
            lines = 1

        command = "k" if up else "j"
        self.signal_cmd.emit(f"{lines}{command}")
        self.signal_cmd.emit("^")

    def pg_half_up(self):
        """Scroll half page up."""
        self._scroll(True, True)

    def pg_up(self):
        """Scroll one page up."""
        self._scroll(False, True)

    def pg_half_down(self):
        """Scroll half page down."""
        self._scroll(True, False)

    def pg_down(self):
        """Scroll one page down."""
        self._scroll(False, False)

    def _extract_number(self) -> tuple[int | None, int, int]:
        """Return the number under the cursor.

        Returns:
            tuple[int | None, int, int]: Extracted number and its start and end
            positions.
        """
        cursor = self.get_editor().textCursor()

        val = None
        block_start = cursor.block().position()
        block_end = block_start + cursor.block().length()
        pos_start = cursor.position()
        pos_end = pos_start

        for index_end in range(pos_start + 1, block_end):
            cursor.setPosition(pos_start)
            cursor.setPosition(index_end, QTextCursor.KeepAnchor)
            try:
                text_selected = cursor.selectedText()
                if text_selected == "-":
                    continue
                val_ = int(text_selected)
                if text_selected.isdigit() or text_selected[0] == "-":
                    val = val_
                    pos_end = index_end
                else:
                    break
            except ValueError:
                break

        for index_start in range(pos_start, block_start - 1, -1):
            cursor.setPosition(index_start)
            cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
            try:
                val_ = int(cursor.selectedText())
                text_selected = cursor.selectedText()
                if text_selected.isdigit() or text_selected[0] == "-":
                    val = val_
                    pos_start = index_start
                else:
                    break
            except ValueError:
                break

        return val, pos_start, pos_end

    def _change_number(self, delta: int, key: int) -> None:
        """Change the number at the cursor.

        Args:
            delta: Increment or decrement value.
            key: Qt key code used for dot command updates.
        """
        val, start, end = self._extract_number()
        if val is None:
            return
        if self.vim_status.sub_mode:
            self.cmd_line.esc_pressed()
            return

        count_text = self.cmd_line.text()
        count = 1 if not count_text else int(count_text)

        cursor = self.get_editor().textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.insertText(str(val + delta * count))
        self.signal_cmd.emit("h")

        cmd_info = InputCmdInfo(str(count), "")
        self.vim_status.input_cmd.set(cmd_info)
        key_info = KeyInfo(key, "", Qt.ControlModifier, 0)
        self.vim_status.update_dot_cmd(False, key_list_to_cmd_line=[key_info])

    def add_num(self) -> None:
        """Add to the number at the cursor."""
        self._change_number(1, Qt.Key_A)

    def subtract_num(self) -> None:
        """Subtract from the number at the cursor."""
        self._change_number(-1, Qt.Key_X)

    def redo(self) -> None:
        """Redo [count] changes which were undone."""
        if self.vim_status.sub_mode:
            self.cmd_line.esc_pressed()
            return

        if not self.vim_status.is_normal():
            return

        editor = self.vim_status.get_editor()
        n_block_old = editor.blockCount()

        txt = self.cmd_line.text()
        num = 1 if not txt else int(txt)

        editor = self.get_editor()
        for _ in range(num):
            editor.redo()

        n_block_new = editor.blockCount()
        if n_block_new != n_block_old:
            if n_block_new > n_block_old:
                self.vim_status.set_message(f"{n_block_new - n_block_old} more lines")
            else:
                self.vim_status.set_message(f"{n_block_old - n_block_new} fewer lines")
        else:
            self.vim_status.set_message(f"{num} changes")

        self.cmd_line.esc_pressed()

    def open_file_search(self) -> None:
        """Open the file search dialog."""
        root_folder = self.main.projects.get_active_project_path()

        dlg = FileSearchDialog(root_folder, self.get_editor().window())
        exec_dialog(dlg)
        path = dlg.get_selected_path()

        if osp.isfile(path):
            self.vim_status.push_jump()
            application = self.main.get_plugin(Plugins.Application)
            application.open_file_in_plugin(path)
            self.vim_status.jump_list.push(path, 0)
        self.vim_status.set_focus_to_vim()

    def clear_tip_search(self) -> None:
        """Clear tooltip, search highlight."""
        self.get_editor().hide_tooltip()
        self.vim_status.search.clear_highlights()

    def jump_backward(self) -> None:
        """Jump to previous location in the jumplist."""
        if self.vim_status.sub_mode:
            self.cmd_line.esc_pressed()
            return
        self.vim_status.jump_backward()
        self.vim_status.set_focus_to_vim()

    def jump_forward(self) -> None:
        """Jump to next location in the jumplist."""
        if self.vim_status.sub_mode:
            self.cmd_line.esc_pressed()
            return
        self.vim_status.jump_forward()
        self.vim_status.set_focus_to_vim()

    def window_command(self) -> None:
        """Wait for an editor split command after Ctrl+w."""
        if self.vim_status.sub_mode:
            self.cmd_line.esc_pressed()
            return
        if not self.vim_status.is_normal():
            return
        count = self.cmd_line.text()
        self.vim_status.input_cmd.set(InputCmdInfo(count, "<C-w>"))
        self.executor_window.parent_num = [int(count) if count else 1]
        self.vim_status.sub_mode = self.executor_window
        self.cmd_line.clear()


class VimStateLabel(QLabel):
    """Display state of vim."""

    def __init__(self, parent):
        super().__init__(parent)
        self.change_state(VimState.INSERT)

        self.setAlignment(Qt.AlignCenter)
        tw = text_width(self.fontMetrics(), " NORMAL ")
        fw = self.style().pixelMetric(QStyle.PM_DefaultFrameWidth)
        self.setFixedWidth(tw + (2 * fw) + 4)

    @Slot(int)
    def change_state(self, state):
        """Display the state of vim."""
        try:
            if widget_is_deleted(self):
                return
            self.setStyleSheet("QLabel { color: white }")
            if state == VimState.VISUAL:
                self.setText("VISUAL")
                self.setStyleSheet("QLabel { background-color: #ff8000 }")
            elif state == VimState.NORMAL:
                self.setText("NORMAL")
                self.setStyleSheet("QLabel { background-color: #29a329 }")
            elif state == VimState.VLINE:
                self.setText("V-LINE")
                self.setStyleSheet("QLabel { background-color: #ff8000 }")
            elif state == VimState.INSERT:
                self.setText("INSERT")
                self.setStyleSheet("QLabel { background-color: #3366ff }")
        except RuntimeError:
            # Ignore updates to deleted widgets
            pass


class VimLineEdit(QLineEdit):
    """Vim Command input."""

    def __init__(self, vim_widget, vim_status: VimStatus, vim_shortcut: VimShortcut):
        super().__init__(vim_widget)
        self.vim_widget = vim_widget
        self.vim_status = vim_status
        self.vim_shortcut = vim_shortcut
        self.histories = {"ex": [], "search": []}
        self._history_index = None
        self._history_draft = None
        self._completion_candidates = []
        self._completion_index = -1
        self._completion_directory = None
        self._updating_commandline = False
        self._is_composing = False
        self._prompt_focus_window = None
        self.textChanged.connect(self._reset_navigation)
        self.cursorPositionChanged.connect(self._reset_completion)

        # Set size
        tw = text_width(self.fontMetrics(), " :%s/international/internationl/g ")
        fw = self.style().pixelMetric(QStyle.PM_DefaultFrameWidth)
        self.setFixedWidth(tw + (2 * fw) + 4)

        # Todo: Move setting shortcut to config file.
        vim_shortcut.signal_cmd.connect(self.setText)
        self.dispatcher = {
            Qt.Key_A: vim_shortcut.add_num,
            Qt.Key_X: vim_shortcut.subtract_num,
            Qt.Key_D: vim_shortcut.pg_half_down,
            Qt.Key_F: vim_shortcut.pg_down,
            Qt.Key_U: vim_shortcut.pg_half_up,
            Qt.Key_B: vim_shortcut.pg_up,
            Qt.Key_R: vim_shortcut.redo,
            Qt.Key_P: vim_shortcut.open_file_search,
            Qt.Key_C: vim_shortcut.clear_tip_search,
            Qt.Key_O: vim_shortcut.jump_backward,
            Qt.Key_I: vim_shortcut.jump_forward,
            Qt.Key_W: vim_shortcut.window_command,
        }
        self.setAttribute(Qt.WA_InputMethodEnabled, False)

    def _reset_navigation(self, text="") -> None:
        """Discard navigation state when the user edits or leaves a prompt."""
        if not self._updating_commandline:
            self._history_index = None
            self._history_draft = None
            self._completion_candidates = []
            self._completion_index = -1

    def _reset_completion(self, old_position, new_position) -> None:
        """A manually moved caret starts a new completion at that position."""
        if not self._updating_commandline:
            self._completion_candidates = []
            self._completion_index = -1

    def _history_context(self, text):
        """Return the history kind, current prompt/count, and editable body."""
        kind = getattr(self.vim_status.sub_mode, "history_kind", None)
        if kind == "ex" and text.startswith(":"):
            return kind, ":", text[1:]
        if kind == "search":
            match = re.fullmatch(r"(\d*[/?])(.*)", text, re.DOTALL)
            if match:
                return kind, *match.groups()
        return None

    def remember_command(self, text) -> None:
        """Keep confirmed, nonempty inputs in separate bounded histories."""
        context = self._history_context(text)
        if context is None:
            return
        kind, _, body = context
        if not body or (kind == "ex" and not body.strip()):
            return
        history = self.histories[kind]
        if not history or history[-1] != body:
            history.append(body)
            del history[:-100]

    def _replace_commandline(self, text, cursor_position=None) -> None:
        """Update a recalled/completed input without restarting navigation."""
        with self.vim_widget.input_processing():
            self._updating_commandline = True
            try:
                self.setText(text)
                if cursor_position is not None:
                    self.setCursorPosition(cursor_position)
            finally:
                self._updating_commandline = False

    def _browse_history(self, backward) -> None:
        """Recall entries and restore the exact draft after the newest one."""
        context = self._history_context(self.text())
        if context is None:
            return
        self.vim_widget.commandline_popup.suppress_history()
        kind, prompt, _ = context
        history = self.histories[kind]
        if not history:
            return
        if self._history_index is None:
            if not backward:
                return
            self._history_draft = (self.text(), self.cursorPosition())
            self._history_index = len(history)
        self._completion_candidates = []
        self._completion_index = -1
        if backward:
            self._history_index = max(0, self._history_index - 1)
        else:
            self._history_index += 1
        if self._history_index >= len(history):
            self._replace_commandline(*self._history_draft)
            self._history_index = None
            self._history_draft = None
        else:
            self._replace_commandline(prompt + history[self._history_index])

    def _complete_commandline(self, backward=False) -> None:
        """Complete Ex commands or one directory of paths on explicit Tab."""
        context = self._history_context(self.text())
        if context is None:
            return
        self.vim_widget.commandline_popup.suppress_history()
        if context[0] != "ex":
            return
        working_directory = os.getcwd()
        if self._completion_directory != working_directory:
            self._completion_candidates = []
        if not self._completion_candidates:
            self._completion_directory = working_directory
            # Qt cursor offsets count UTF-16 units; the helper uses Python indices.
            cursor = len(
                self.text()
                .encode("utf-16-le")[: self.cursorPosition() * 2]
                .decode("utf-16-le", errors="ignore")
            )
            self._completion_candidates = completion_candidates(
                self.text(),
                cursor,
                self.vim_status.sub_mode.SUPPORTED_COMMANDS,
                working_directory,
            )
            self._completion_index = (
                len(self._completion_candidates) - 1 if backward else 0
            )
        else:
            step = -1 if backward else 1
            self._completion_index = (self._completion_index + step) % len(
                self._completion_candidates
            )
        if not self._completion_candidates:
            return
        text, cursor = self._completion_candidates[self._completion_index]
        qt_cursor = len(text[:cursor].encode("utf-16-le")) // 2
        self._replace_commandline(text, qt_cursor)
        # A unique directory can be traversed with the next Tab.
        if len(self._completion_candidates) == 1:
            self._completion_candidates = []

    def event(self, event) -> bool:
        """Keep Tab in the prompt instead of letting QWidget move focus."""
        if (
            event.type() == QEvent.ShortcutOverride
            and self.vim_widget.commandline_popup.key_action(event) is not None
        ):
            event.accept()
            return True
        if self.vim_status.substitute_confirm is not None:
            if event.type() == QEvent.ShortcutOverride:
                event.accept()
                return True
            if event.type() == QEvent.KeyPress:
                self.keyPressEvent(event)
                return True
        if (
            event.type() == QEvent.ShortcutOverride
            and event.modifiers() == Qt.ControlModifier
            and event.key() in (Qt.Key_P, Qt.Key_N)
            and self._yank_cycle_context()
            and self.vim_widget.put_controller.can_cycle()
        ):
            # Reserve a valid cycle without editing during ShortcutOverride.
            event.accept()
            return True
        if (
            event.type() == QEvent.KeyPress
            and event.key() in (Qt.Key_Tab, Qt.Key_Backtab)
            and self._history_context(self.text()) is not None
        ):
            self.keyPressEvent(event)
            return True
        return super().event(event)

    def inputMethodQuery(self, query):
        """Report mode-specific IME availability to the native input context."""
        if query == Qt.ImEnabled:
            # Qt 6 QLineEdit reports ImEnabled independently of this attribute.
            return (
                self.testAttribute(Qt.WA_InputMethodEnabled)
                and self.isEnabled()
                and not self.isReadOnly()
            )
        return super().inputMethodQuery(query)

    def sync_input_method(self) -> None:
        """Allow composition only while entering search or Ex text."""
        enabled = bool(
            self.vim_status.sub_mode and self.vim_status.sub_mode.accepts_input_method
        )
        if enabled == self.testAttribute(Qt.WA_InputMethodEnabled):
            return
        # Disable delivery before resetting: some IMEs commit on reset.
        self.setAttribute(Qt.WA_InputMethodEnabled, enabled)
        if not enabled:
            self._is_composing = False
            if self.hasFocus():
                QApplication.inputMethod().reset()
            super().inputMethodEvent(QInputMethodEvent())

    def inputMethodEvent(self, event: QInputMethodEvent) -> None:
        """Keep late IME commits from being interpreted as Normal commands."""
        if self.testAttribute(Qt.WA_InputMethodEnabled):
            with self.vim_widget.input_processing():
                self._is_composing = bool(event.preeditString())
                super().inputMethodEvent(event)
        else:
            event.ignore()

    @property
    def is_composing(self):
        """Whether the native input method still owns uncommitted text."""
        return self._is_composing

    def to_normal(self) -> None:
        """Convert the state of vim to normal mode."""
        self.clear()
        self.vim_widget.vim_status.to_normal()
        self.vim_widget.vim_status.cursor.draw_vim_cursor()

    def keyPressEvent(self, e: QKeyEvent) -> None:
        """Override Qt method."""
        history_action = self.vim_widget.commandline_popup.key_action(e)
        with self.vim_widget.input_processing():
            self._handle_key_press(e, history_action)

    def _handle_key_press(self, e: QKeyEvent, history_action=None) -> None:
        """Process a key before synchronizing hints at the outer input boundary."""
        if history_action is not None:
            self.vim_widget.commandline_popup.handle_key(history_action, e)
            return
        if not self.testAttribute(Qt.WA_InputMethodEnabled):
            e = latin_command_key(e)
        confirmation = self.vim_status.substitute_confirm
        if confirmation is not None:
            if e.key() == Qt.Key_Escape or (
                e.key() == Qt.Key_C and e.modifiers() == Qt.ControlModifier
            ):
                self.esc_pressed()
            elif e.modifiers() in (Qt.NoModifier, Qt.ShiftModifier):
                confirmation(e.text())
            self.clear()
            self.sync_input_method()
            e.accept()
            return
        self.vim_status.manager_macro.add_vim_keyevent(e)

        key = e.key()
        pressed_ctrl = e.modifiers() == Qt.ControlModifier
        if self.try_handle_yank_cycle(e):
            return
        if key == Qt.Key_Escape:
            self.esc_pressed()
        elif pressed_ctrl and key == Qt.Key_C and self._substitute_input():
            self.vim_shortcut.clear_tip_search()
            self.esc_pressed()
        elif pressed_ctrl and key in self.dispatcher.keys():
            self.vim_widget.put_controller.cancel()
            self.dispatcher[key]()
        elif self.testAttribute(Qt.WA_InputMethodEnabled):
            if key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Tab, Qt.Key_Backtab):
                QApplication.inputMethod().commit()
                if key in (Qt.Key_Up, Qt.Key_Down):
                    self._browse_history(key == Qt.Key_Up)
                else:
                    self._complete_commandline(
                        key == Qt.Key_Backtab or bool(e.modifiers() & Qt.ShiftModifier)
                    )
                e.accept()
            elif key in (Qt.Key_Return, Qt.Key_Enter):
                # Flush the final composing syllable before executing the text.
                QApplication.inputMethod().commit()
                self.setText(self.text() + "\r")
            else:
                super().keyPressEvent(e)
        elif KEYCODE2STR.get(key, None):
            self.setText(self.text() + KEYCODE2STR[key])
        else:
            super().keyPressEvent(e)

    def _substitute_input(self):
        """Cancel substitute prompts with Ctrl+C even when preview is disabled."""
        if getattr(self.vim_status.sub_mode, "history_kind", None) != "ex":
            return False
        if not self.text().startswith(":"):
            return False
        try:
            return is_substitute(scan_header(self.text()[1:]).command)
        except ExError:
            return False

    def _yank_cycle_context(self):
        """Only plain Normal input and an optional positive count can cycle."""
        text = self.text()
        return (
            self.vim_status.is_normal()
            and self.vim_status.sub_mode is None
            and self.vim_widget._yank_picker is None
            and (not text or re.fullmatch(r"[1-9][0-9]*", text) is not None)
        )

    def try_handle_yank_cycle(self, event):
        """Consume valid cycles, including endpoints, before the file search."""
        if event.modifiers() != Qt.ControlModifier or event.key() not in (
            Qt.Key_P,
            Qt.Key_N,
        ):
            return False
        in_cycle_context = self._yank_cycle_context()
        handled = in_cycle_context and self.vim_widget.put_controller.cycle(
            1 if event.key() == Qt.Key_P else -1,
            int(self.text()) if self.text() else 1,
        )
        if not handled:
            if not self.vim_widget.is_playing_macro:
                return False
            self.vim_status.set_message("Yanky: no put to cycle in this macro")
        if in_cycle_context:
            self.clear()
            self.vim_status.input_cmd.clear()
        event.accept()
        return True

    def esc_pressed(self) -> None:
        """Clear state."""
        self._prompt_focus_window = None
        self.vim_widget.cancel_substitute()
        self.vim_widget.put_controller.cancel()
        self.vim_widget.sig_command_cancelled.emit()
        self.vim_status.input_cmd.clear()
        self.vim_status.remove_marker_of_easymotion()
        sub_mode = self.vim_status.sub_mode
        if sub_mode:
            try:
                sub_mode.on_escape()
            finally:
                self.vim_status.sub_mode = None
                self.sync_input_method()
                self.clear()
        else:
            self.to_normal()

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Override Qt method."""
        self.vim_status.disconnect_from_editor()
        super().focusInEvent(event)
        preserve_prompt = (
            self._prompt_focus_window is not None
            and self._prompt_focus_window() is self.window()
        )
        self._prompt_focus_window = None
        if preserve_prompt and self._history_context(self.text()) is not None:
            self.vim_widget.substitute_preview.resume()
            self.vim_widget.sig_command_changed.emit()
            return
        if self.vim_widget._yank_picker is not None:
            return
        if self.vim_status.cursor.get_editor():
            self.to_normal()
        self.vim_status.set_message("")
        self.vim_widget.sig_command_changed.emit()

    def _transient_prompt_focus_loss(self, event):
        """Keep an Ex draft across application deactivation or temporary hide."""
        context = self._history_context(self.text())
        return bool(
            context is not None
            and context[0] == "ex"
            and (event.reason() == Qt.ActiveWindowFocusReason or not self.isVisible())
        )

    def focusOutEvent(self, event: QFocusEvent) -> None:
        """Override Qt method."""
        if self._transient_prompt_focus_loss(event):
            if self._prompt_focus_window is None:
                self._prompt_focus_window = weakref.ref(self.window())
            self.vim_widget.substitute_preview.suspend()
            super().focusOutEvent(event)
            return
        self._prompt_focus_window = None
        self.vim_widget.cancel_substitute()
        if self.vim_widget._yank_picker is not None:
            super().focusOutEvent(event)
            return
        self.vim_widget.put_controller.cancel()
        self.vim_widget.sig_command_cancelled.emit()
        if self.testAttribute(Qt.WA_InputMethodEnabled):
            self.esc_pressed()
        super().focusOutEvent(event)
        self.clear()
        try:
            self.vim_widget.vim_status.to_insert()
        except RuntimeError:
            # The status may already be deleted when closing widgets
            pass


class VimMessageLabel(QLabel):
    """Display Vim status messages."""

    def __init__(self, txt, parent):
        super().__init__(txt, parent)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        tw = text_width(self.fontMetrics(), " recording @q... 0000 fewers lines ")
        fw = self.style().pixelMetric(QStyle.PM_DefaultFrameWidth)
        self.setFixedWidth(tw + (2 * fw) + 4)


class MacroPlaybackWorker(QThread):
    """Replay a recorded macro on the main thread."""

    sig_focus_vim = Signal(int)
    sig_send_key_info = Signal(object, int)
    sig_playback_finished = Signal(int)

    def __init__(self, parent: QObject | None) -> None:
        super().__init__(parent)
        self.key_info_list = []
        self.num_iteration = 0
        self.generation = 0

    def set_key_infos(self, key_infos: list[KeyInfo], num: int) -> None:
        """Set key infos of registers."""
        self.generation += 1
        self.key_info_list = key_infos.copy()
        self.num_iteration = num

    @enable_coverage_tracing
    def run(self) -> None:
        """Send key info to main thread."""
        generation = self.generation
        is_focus_vim = True
        for _ in range(self.num_iteration):
            if self.isInterruptionRequested():
                return
            for key_info in self.key_info_list:
                if self.isInterruptionRequested():
                    return
                if key_info.identifier == 1:
                    is_focus_vim = False
                elif key_info.identifier == 0 and is_focus_vim is False:
                    is_focus_vim = True
                    self.sig_focus_vim.emit(generation)
                self.sig_send_key_info.emit(key_info, generation)

        if is_focus_vim is False:
            self.sig_focus_vim.emit(generation)
        # This shares the key signals' sender and queued delivery order.
        self.sig_playback_finished.emit(generation)


class VimWidget(QWidget):
    """Own command dispatch and report its stable input boundaries."""

    sig_input_started = Signal()
    sig_input_finished = Signal()
    sig_command_changed = Signal()
    sig_command_cancelled = Signal()

    def __init__(self, editor_widget, main):
        super().__init__(main)
        self.editor_widget = editor_widget
        self.main = main
        self._input_depth = 0
        self._yank_picker = None
        self.status_label = VimStateLabel(main)
        self.msg_label = VimMessageLabel("", main)

        self.vim_status = VimStatus(editor_widget, main, self.msg_label)
        self.put_controller = PutController(self.vim_status)
        self.vim_status.put_controller = self.put_controller
        # # Avoid Qt crashes if the label is deleted by ignoring the signal
        # self.vim_status.change_label.connect(lambda state: None)
        self.vim_status.change_label.connect(self.status_label.change_state)

        self.vim_shortcut = VimShortcut(self.main, self.vim_status)

        self.commandline = VimLineEdit(self, self.vim_status, self.vim_shortcut)
        self.commandline.textChanged.connect(self.on_text_changed)

        self.vim_status.cmd_line = self.commandline
        self.vim_shortcut.cmd_line = self.commandline

        self.executor_normal_cmd = ExecutorNormalCmd(self.vim_status)
        self.executor_visual_cmd = ExecutorVisualCmd(self.vim_status)
        self.executor_vline_cmd = ExecutorVlineCmd(self.vim_status)
        self.executors = {
            VimState.NORMAL: self.executor_normal_cmd,
            VimState.VISUAL: self.executor_visual_cmd,
            VimState.VLINE: self.executor_vline_cmd,
        }

        # leader key
        self.executor_leader_key = ExecutorLeaderKey(self.vim_status)
        self.leader_key = " "

        # macro
        self._macro_generation = -1
        self._macro_editor = None
        self._macro_completion = None
        self.worker_macro = MacroPlaybackWorker(main)
        self.worker_macro.sig_send_key_info.connect(self.send_key_event)
        self.worker_macro.sig_focus_vim.connect(self._focus_macro_input)
        self.worker_macro.sig_playback_finished.connect(self._finish_macro)
        self.which_key = WhichKeyController(self)
        self.commandline_popup = CommandlinePopupController(self)
        self.substitute_preview = SubstitutePreviewController(self)
        self.apply_settings()

    @property
    def is_processing_input(self):
        """Whether recursive input dispatch still has unfinished work."""
        return self._input_depth > 0

    @property
    def is_playing_macro(self):
        """Whether a macro still has queued GUI input to finish."""
        return self._macro_generation >= 0

    def pending_hint(self):
        """Expose a stable prefix wait independently of the display controller."""
        status = self.vim_status
        executor = status.sub_mode
        if (
            self.is_processing_input
            or self.is_playing_macro
            or status.running_dot_cmd
            or status.vim_state not in self.executors
            or executor is None
            or executor.hint_prefix is None
        ):
            return None
        editor = status.get_editor()
        if editor is None or widget_is_deleted(editor):
            return None
        return PendingHint(
            weakref.ref(editor), executor, status.vim_state, executor.hint_prefix
        )

    def apply_settings(self):
        """Apply command bindings and hint preferences explicitly."""
        self.set_leader_key()
        self.which_key.apply_settings()
        self.commandline_popup.apply_settings()
        self.substitute_preview.apply_settings()
        status = self.vim_status
        enabled = bool(CONF.get(CONF_SECTION, "yanky_enabled", True))
        length = CONF.get(CONF_SECTION, "yank_history_length", 100)
        if not isinstance(length, int) or isinstance(length, bool) or length < 1:
            length = 100
        if enabled != status.yanky_enabled or length != status.yank_history.length:
            self.cancel_yank_picker()
            self.put_controller.cancel()
        status.yanky_enabled = enabled
        status.yank_history.resize(length)
        status.cursor.set_config_from_conf()

    def clear_yank_history(self):
        """Clear memory explicitly, including while Yanky is disabled."""
        self.cancel_yank_picker()
        self.put_controller.cancel()
        self.vim_status.yank_history.clear()
        self.vim_status.set_message("Yanky: history cleared")

    def cancel_yank_picker(self):
        """Invalidate callbacks before closing a popup that may delete itself."""
        picker, self._yank_picker = self._yank_picker, None
        if picker is not None:
            picker.cancel()

    def cancel_substitute(self):
        """End a pending confirmation without undoing accepted replacements."""
        confirmation = self.vim_status.substitute_confirm
        if confirmation is not None:
            confirmation.cancel()

    def show_yank_history(self):
        """Pick one immutable history entry against a captured editor context."""
        status = self.vim_status
        self.cancel_yank_picker()
        self.put_controller.cancel()
        if not status.yanky_enabled:
            status.set_message("Yanky is disabled")
            return
        if self.is_playing_macro or status.is_recording_macro():
            status.set_message("Yanky: history picker is unavailable in macros")
            return
        editor = status.get_editor()
        if editor is None or widget_is_deleted(editor) or editor.isReadOnly():
            return
        entries = status.yank_history.snapshot()
        if not entries:
            status.set_message("Yanky: history is empty")
            return
        self.put_controller.bind_editor(editor)
        self._yank_picker = YankHistoryPicker(self, editor, entries)
        self._yank_picker.show()

    @contextmanager
    def input_processing(self):
        """Synchronize hints once, after recursive command processing finishes."""
        self._input_depth += 1
        if self._input_depth == 1:
            self.sig_input_started.emit()
        try:
            yield
        except BaseException:
            self.put_controller.cancel()
            raise
        finally:
            self._input_depth -= 1
            if self._input_depth == 0:
                if self._macro_completion is not None:
                    self._finish_macro(self._macro_completion)
                self.sig_input_finished.emit()

    def cancel_macro(self) -> None:
        """Invalidate queued playback when its editor is left or closed."""
        self.put_controller.cancel()
        self._macro_generation = -1
        self._macro_editor = None
        self._macro_completion = None
        self.worker_macro.requestInterruption()
        self.sig_command_cancelled.emit()

    def _macro_is_current(self, generation) -> bool:
        return (
            generation == self._macro_generation
            and self._macro_editor is not None
            and self._macro_editor() is self.vim_status.get_editor()
        )

    @Slot(int)
    def _focus_macro_input(self, generation) -> None:
        if self._macro_is_current(generation):
            self.commandline.setFocus()

    @Slot(int)
    def _finish_macro(self, generation) -> None:
        """Release hint suppression after the last queued key has been handled."""
        if not self._macro_is_current(generation):
            return
        if self._input_depth:
            self._macro_completion = generation
            return
        self._macro_completion = None
        self._macro_generation = -1
        self._macro_editor = None
        self.put_controller.cancel()
        self.sig_command_changed.emit()

    @Slot(object, int)
    def send_key_event(self, key_info: KeyInfo, generation=None) -> None:
        if generation is not None and not self._macro_is_current(generation):
            return
        with self.input_processing():
            event = key_info.to_event()
            if key_info.identifier == 0:
                self.commandline.keyPressEvent(event)
            else:
                editor = self.vim_status.get_editor()
                self.vim_status.send_insert_event(editor, event)

    def set_leader_key(self) -> None:
        """Set leader key from CONF."""
        leader_key = CONF.get(CONF_SECTION, "leader_key")
        key_sequence = QKeySequence.fromString(leader_key)
        try:
            key = key_sequence[0]
        except (IndexError, TypeError):
            key = None
        if hasattr(key, "key"):
            # PySide6 returns QKeyCombination objects; extract the raw key.
            key = key.key()
        leader_key2 = KEYCODE2STR.get(key, None)
        if leader_key2:
            leader_key = leader_key2
        changed = self.leader_key != leader_key
        self.leader_key = leader_key
        self.executor_leader_key.set_easymotion_key(leader_key)
        if changed:
            self.sig_command_changed.emit()

    def on_text_changed(self, txt: str) -> None:
        """Send input command to executor."""
        with self.input_processing():
            self._process_text(txt)

    def _process_text(self, txt: str) -> None:
        """Run existing executors while recursive clears stay inside the guard."""
        if not txt:
            sub_mode = self.vim_status.sub_mode
            if sub_mode and sub_mode.accepts_input_method:
                self.commandline.esc_pressed()
            self.commandline.sync_input_method()
            return

        confirmation = self.vim_status.substitute_confirm
        if confirmation is not None:
            confirmation(txt)
            self.commandline.clear()
            self.commandline.sync_input_method()
            return

        if not (
            self.vim_status.is_normal()
            and self.vim_status.sub_mode is None
            and re.fullmatch(r"[1-9][0-9]*", txt)
        ):
            self.put_controller.cancel()

        executor = self.executors[self.vim_status.vim_state]
        if self.vim_status.sub_mode:
            executor = self.vim_status.sub_mode

        # workaround for easymotion (press leader, leader)
        if txt == self.leader_key and executor != self.executor_leader_key:
            sub_mode = self.vim_status.sub_mode
            if sub_mode and sub_mode.allow_leaderkey is False:
                pass
            else:
                self.executor_leader_key.prev_executor = executor
                self.vim_status.sub_mode = self.executor_leader_key
                self.commandline.clear()
                return

        if txt.endswith("\r"):
            self.substitute_preview.cancel()
            self.commandline.remember_command(txt[:-1])
        if executor(txt):
            self.commandline.clear()

        # Visual ':' captures rows before leaving Visual mode. Install its
        # executor first: setText emits textChanged synchronously and otherwise
        # re-enters the previous executor with the numeric range.
        sub_mode = self.vim_status.sub_mode
        if sub_mode is not executor and getattr(sub_mode, "history_kind", None) == "ex":
            sub_mode.begin_input()
            self.substitute_preview.begin_session(sub_mode)
        pending_range = getattr(sub_mode, "pending_range_text", None)
        if pending_range is not None:
            sub_mode.pending_range_text = None
            self.commandline.setText(pending_range)

        self.commandline.sync_input_method()

        if self.vim_status.manager_macro.reg_name_for_execute:
            self.put_controller.cancel()
            mm = self.vim_status.manager_macro
            ch = mm.reg_name_for_execute
            if self.worker_macro.isRunning():
                self.worker_macro.requestInterruption()
                self.worker_macro.wait()
            self.worker_macro.set_key_infos(mm.registers[ch], mm.num_execute)
            self._macro_generation = self.worker_macro.generation
            self._macro_editor = weakref.ref(self.vim_status.get_editor())
            self._macro_completion = None
            self.sig_command_cancelled.emit()
            self.worker_macro.start()
            mm.set_info_for_execute("", 0)

    def cleanup(self) -> None:
        """Clean up resources used by the widget."""
        self.substitute_preview.cleanup()
        self.cancel_substitute()
        self.cancel_yank_picker()
        self.put_controller.cleanup()
        self.which_key.cleanup()
        self.commandline_popup.cleanup()
        self.cancel_macro()
        if self.vim_status.is_recording_macro():
            self.vim_status.stop_recording_macro()
        self.vim_status.finish_insert(apply_count=False)
        self.vim_status.search.close()
        try:
            self.vim_status.change_label.disconnect(self.status_label.change_state)
        except Exception:
            pass
        if self.worker_macro.isRunning():
            self.worker_macro.quit()
            self.worker_macro.wait()
        if running_in_pytest():
            self.worker_macro.deleteLater()
            self.commandline.deleteLater()
            self.status_label.deleteLater()
            self.msg_label.deleteLater()
