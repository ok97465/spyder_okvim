# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) Spyder Project Contributors
#
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
# -----------------------------------------------------------------------------
"""OkVim Widget."""

# Standard Libraries
import os.path as osp
import sys
import threading
from functools import wraps

# Third Party Libraries
from qtpy import PYSIDE2, PYSIDE6
from qtpy.QtCore import QObject, Qt, QThread, Signal, Slot
from qtpy.QtGui import QFocusEvent, QKeyEvent, QKeySequence, QTextCursor
from qtpy.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QWidget
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
from spyder_okvim.spyder.config import CONF_SECTION, KEYCODE2STR
from spyder_okvim.utils.file_search import FileSearchDialog
from spyder_okvim.utils.testing_env import running_in_pytest
from spyder_okvim.vim import InputCmdInfo, KeyInfo, VimState, VimStatus

running_coverage = "coverage" in sys.modules


if PYSIDE2 or PYSIDE6:
    try:
        # Third Party Libraries
        from shiboken6 import isValid as _sbk_is_valid  # PySide6
    except Exception:
        try:
            # Third Party Libraries
            from shiboken2 import isValid as _sbk_is_valid  # PySide2
        except Exception:
            _sbk_is_valid = None

    def _widget_is_deleted(obj):
        if _sbk_is_valid is None:
            return False
        return not _sbk_is_valid(obj)
else:  # PYQT5
    try:
        # Third Party Libraries
        from PyQt5 import sip
    except Exception:  # pragma: no cover - fallback for standalone sip module
        try:
            # Third Party Libraries
            import sip  # type: ignore
        except Exception:
            sip = None

    def _widget_is_deleted(obj):
        if sip is None:
            return False
        return sip.isdeleted(obj)


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
        self.vim_cmd.vim_status.cursor.set_config_from_conf()
        self.vim_cmd.set_leader_key()


class VimShortcut(QObject):
    """Method class for vim shortcut."""

    signal_cmd = Signal(str)

    def __init__(self, main, vim_status: VimStatus):
        super().__init__()
        self.main = main
        self.vim_status = vim_status
        self.get_editor = self.vim_status.get_editor
        self.cmd_line = None

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

        dlg = FileSearchDialog(root_folder, self.main)
        dlg.exec_()
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
        self.vim_status.cursor.set_extra_selections("vim_search", [])

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


class VimStateLabel(QLabel):
    """Display state of vim."""

    def __init__(self, parent):
        super().__init__(parent)
        self.change_state(VimState.INSERT)

        self.setAlignment(Qt.AlignCenter)
        tw = self.fontMetrics().width(" NORMAL ")
        fw = self.style().pixelMetric(self.style().PM_DefaultFrameWidth)
        self.setFixedWidth(tw + (2 * fw) + 4)

    @Slot(int)
    def change_state(self, state):
        """Display the state of vim."""
        try:
            if _widget_is_deleted(self):
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

        # Set size
        tw = self.fontMetrics().width(" :%s/international/internationl/g ")
        fw = self.style().pixelMetric(self.style().PM_DefaultFrameWidth)
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
        }
        self.setAttribute(Qt.WA_InputMethodEnabled, False)

    def to_normal(self) -> None:
        """Convert the state of vim to normal mode."""
        self.clear()
        self.vim_widget.vim_status.to_normal()
        self.vim_widget.vim_status.cursor.draw_vim_cursor()

    def keyPressEvent(self, e: QKeyEvent) -> None:
        """Override Qt method."""
        self.vim_status.manager_macro.add_vim_keyevent(e)

        key = e.key()
        pressed_ctrl = e.modifiers() == Qt.ControlModifier
        if key == Qt.Key_Escape:
            self.esc_pressed()
        elif KEYCODE2STR.get(key, None):
            self.setText(self.text() + KEYCODE2STR[key])
        elif pressed_ctrl and key in self.dispatcher.keys():
            self.dispatcher[key]()
        else:
            super().keyPressEvent(e)

    def esc_pressed(self) -> None:
        """Clear state."""
        self.vim_status.input_cmd.clear()
        self.vim_status.remove_marker_of_easymotion()
        if self.vim_status.sub_mode:
            self.vim_status.sub_mode = None
            self.clear()
        else:
            self.to_normal()

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Override Qt method."""
        self.vim_status.disconnect_from_editor()
        super().focusInEvent(event)
        if self.vim_status.cursor.get_editor():
            self.to_normal()
        self.vim_status.set_message("")

    def focusOutEvent(self, event: QFocusEvent) -> None:
        """Override Qt method."""
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
        tw = self.fontMetrics().width(" recording @q... 0000 fewers lines ")
        fw = self.style().pixelMetric(self.style().PM_DefaultFrameWidth)
        self.setFixedWidth(tw + (2 * fw) + 4)


class MacroPlaybackWorker(QThread):
    """Replay a recorded macro on the main thread."""

    sig_focus_vim = Signal()
    sig_send_key_info = Signal(object)

    def __init__(self, parent: QObject | None) -> None:
        super().__init__(parent)
        self.key_info_list = []
        self.num_iteration = 0

    def set_key_infos(self, key_infos: list[KeyInfo], num: int) -> None:
        """Set key infos of registers."""
        self.key_info_list = key_infos.copy()
        self.num_iteration = num

    @enable_coverage_tracing
    def run(self) -> None:
        """Send key info to main thread."""
        is_focus_vim = True
        for _ in range(self.num_iteration):
            for key_info in self.key_info_list:
                if key_info.identifier == 1:
                    is_focus_vim = False
                elif key_info.identifier == 0 and is_focus_vim is False:
                    is_focus_vim = True
                    self.sig_focus_vim.emit()
                self.sig_send_key_info.emit(key_info)

        if is_focus_vim is False:
            self.sig_focus_vim.emit()


class VimWidget(QWidget):
    """Vim widget."""

    def __init__(self, editor_widget, main):
        super().__init__(main)
        self.editor_widget = editor_widget
        self.main = main
        self.status_label = VimStateLabel(main)
        self.msg_label = VimMessageLabel("", main)

        self.vim_status = VimStatus(editor_widget, main, self.msg_label)
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
        self.set_leader_key()

        # macro
        self.worker_macro = MacroPlaybackWorker(main)
        self.worker_macro.sig_send_key_info.connect(self.send_key_event)
        self.worker_macro.sig_focus_vim.connect(self.commandline.setFocus)

    @Slot(object)
    def send_key_event(self, key_info: KeyInfo) -> None:
        event = key_info.to_event()
        if key_info.identifier == 0:
            self.commandline.keyPressEvent(event)
        else:
            editor = self.vim_status.get_editor()
            editor.keyPressEvent(event)

    def set_leader_key(self) -> None:
        """Set leader key from CONF."""
        leader_key = CONF.get(CONF_SECTION, "leader_key")
        leader_key2 = KEYCODE2STR.get(QKeySequence.fromString(leader_key)[0], None)
        if leader_key2:
            leader_key = leader_key2
        self.leader_key = leader_key
        self.executor_leader_key.set_easymotion_key(self.leader_key)

    def on_text_changed(self, txt: str) -> None:
        """Send input command to executor."""
        if not txt:
            return

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

        if executor(txt):
            self.commandline.clear()

        if self.vim_status.manager_macro.reg_name_for_execute:
            mm = self.vim_status.manager_macro
            ch = mm.reg_name_for_execute
            self.worker_macro.set_key_infos(mm.registers[ch], mm.num_execute)
            self.worker_macro.start()
            mm.set_info_for_execute("", 0)

    def cleanup(self) -> None:
        """Clean up resources used by the widget."""
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
