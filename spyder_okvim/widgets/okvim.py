# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) Spyder Project Contributors
#
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
# -----------------------------------------------------------------------------
"""OkVim Widget."""
# %% Import
# Standard library imports
import sys
import threading
import os.path as osp
from functools import wraps

# Third party imports
from qtpy.QtCore import QObject, Qt, QThread, Signal, Slot
from qtpy.QtGui import QKeySequence, QTextCursor
from qtpy.QtWidgets import QLabel, QLineEdit, QWidget
from spyder.config.manager import CONF

# Local imports
from spyder_okvim.config import CONF_SECTION, KEYCODE2STR
from spyder_okvim.executor import (
    ExecutorLeaderKey, ExecutorNormalCmd, ExecutorVisualCmd, ExecutorVlineCmd,)
from spyder_okvim.utils.vim_status import (
    InputCmdInfo, KeyInfo, VimState, VimStatus,)
from spyder_okvim.utils.path_finder import PathFinder

running_coverage = 'coverage' in sys.modules


def coverage_resolve_trace(fn):
    """Fix missing coverage of qthread."""
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if running_coverage:
            sys.settrace(threading._trace_hook)
        fn(*args, **kwargs)
    return wrapped


class VimShortcut(QObject):
    """Method class for vim shortcut."""

    signal_cmd = Signal(str)

    def __init__(self, main, vim_status: VimStatus):
        super().__init__()
        self.main = main
        self.vim_status = vim_status
        self.get_editor = self.vim_status.get_editor
        self.cmd_line = None

    def pg_half_up(self):
        """Scroll window upward."""
        scroll_lines = self.vim_status.get_number_of_visible_lines() // 2
        if scroll_lines < 1:
            scroll_lines = 1

        self.signal_cmd.emit(f"{scroll_lines}k")
        self.signal_cmd.emit("^")

    def pg_up(self):
        """Scroll window upward."""
        scroll_lines = self.vim_status.get_number_of_visible_lines()
        if scroll_lines < 1:
            scroll_lines = 1

        self.signal_cmd.emit(f"{scroll_lines}k")
        self.signal_cmd.emit("^")

    def pg_half_down(self):
        """Scroll window downward."""
        scroll_lines = self.vim_status.get_number_of_visible_lines() // 2
        if scroll_lines < 1:
            scroll_lines = 1

        self.signal_cmd.emit(f"{scroll_lines}j")
        self.signal_cmd.emit("^")

    def pg_down(self):
        """Scroll window downward."""
        scroll_lines = self.vim_status.get_number_of_visible_lines()
        if scroll_lines < 1:
            scroll_lines = 1

        self.signal_cmd.emit(f"{scroll_lines}j")
        self.signal_cmd.emit("^")

    def _extract_number(self):
        """Extract the number of current cursor position."""
        cursor = self.get_editor().textCursor()

        val = None
        block_start = cursor.block().position()
        block_end = block_start + cursor.block().length()
        pos_start = cursor.position()
        pos_end = pos_start

        for _pos_end in range(pos_start + 1, block_end):
            cursor.setPosition(pos_start)
            cursor.setPosition(_pos_end, QTextCursor.KeepAnchor)
            try:
                text_selected = cursor.selectedText()
                if text_selected == '-':
                    continue
                val_ = int(text_selected)
                if text_selected.isdigit() or text_selected[0] == '-':
                    val = val_
                    pos_end = _pos_end
                else:
                    break
            except ValueError:
                break

        for _pos_start in range(pos_start, block_start - 1, -1):
            cursor.setPosition(_pos_start)
            cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
            try:
                val_ = int(cursor.selectedText())
                text_selected = cursor.selectedText()
                if text_selected.isdigit() or text_selected[0] == '-':
                    val = val_
                    pos_start = _pos_start
                else:
                    break
            except ValueError:
                break

        return val, pos_start, pos_end

    def add_num(self):
        """Add to the number at the cursor."""
        val, pos_start, pos_end = self._extract_number()

        if val is not None:
            if self.vim_status.sub_mode:
                self.cmd_line.esc_pressed()
                return

            txt = self.cmd_line.text()
            num = 1 if not txt else int(txt)

            cursor = self.get_editor().textCursor()
            cursor.setPosition(pos_start)
            cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
            cursor.insertText(str(val + num))
            self.signal_cmd.emit("h")

            # Update dot cmd
            cmd_info = InputCmdInfo(str(num), "")
            self.vim_status.input_cmd.set(cmd_info)
            key_info = KeyInfo(Qt.Key_A, '', Qt.ControlModifier, 0)
            self.vim_status.update_dot_cmd(
                    False, key_list_to_cmd_line=[key_info])

    def subtract_num(self):
        """Subtract to the number at the cursor."""
        val, pos_start, pos_end = self._extract_number()

        if val is not None:
            if self.vim_status.sub_mode:
                self.cmd_line.esc_pressed()
                return

            txt = self.cmd_line.text()
            num = 1 if not txt else int(txt)

            cursor = self.get_editor().textCursor()
            cursor.setPosition(pos_start)
            cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
            cursor.insertText(str(val - num))
            self.signal_cmd.emit("h")

            # Update dot cmd
            cmd_info = InputCmdInfo(str(num), "")
            self.vim_status.input_cmd.set(cmd_info)
            key_info = KeyInfo(Qt.Key_X, '', Qt.ControlModifier, 0)
            self.vim_status.update_dot_cmd(
                    False, key_list_to_cmd_line=[key_info])

    def redo(self):
        """ Redo [count] changes which were undone. """
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
                self.vim_status.set_message(
                    f"{n_block_new - n_block_old} more lines")
            else:
                self.vim_status.set_message(
                    f"{n_block_old - n_block_new} fewer lines")
        else:
            self.vim_status.set_message(f"{num} changes")

        self.cmd_line.esc_pressed()

    def open_path_finder(self):
        """Open path finder."""
        root_folder = self.main.projects.get_active_project_path()

        dlg = PathFinder(root_folder, self.main)
        dlg.exec_()
        path = dlg.get_path_selected()

        if osp.isfile(path):
            self.main.open_file(path)
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


class VimLineEdit(QLineEdit):
    """Vim Command input."""

    def __init__(self, vim_widget, vim_status: VimStatus,
                 vim_shortcut: VimShortcut):
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
        self.dispatcher = {Qt.Key_A: vim_shortcut.add_num,
                           Qt.Key_X: vim_shortcut.subtract_num,
                           Qt.Key_D: vim_shortcut.pg_half_down,
                           Qt.Key_F: vim_shortcut.pg_down,
                           Qt.Key_U: vim_shortcut.pg_half_up,
                           Qt.Key_B: vim_shortcut.pg_up,
                           Qt.Key_R: vim_shortcut.redo,
                           Qt.Key_P: vim_shortcut.open_path_finder}

    def to_normal(self):
        """Convert the state of vim to normal mode."""
        self.clear()
        self.vim_widget.vim_status.to_normal()
        self.vim_widget.vim_status.cursor.draw_vim_cursor()

    def keyPressEvent(self, e):
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

    def esc_pressed(self):
        """Clear state."""
        self.vim_status.input_cmd.clear()
        if self.vim_status.sub_mode:
            self.vim_status.sub_mode = None
            self.clear()
        else:
            self.to_normal()

    def focusInEvent(self, event):
        """Override Qt method."""
        self.vim_status.disconnect_from_editor()
        super().focusInEvent(event)
        self.to_normal()
        self.vim_status.set_message("")

    def focusOutEvent(self, event):
        """Override Qt method."""
        super().focusInEvent(event)
        self.clear()
        self.vim_widget.vim_status.to_insert()


class VimMsgLabel(QLabel):
    """Display message of vim."""

    def __init__(self, txt, parent):
        super().__init__(txt, parent)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        tw = self.fontMetrics().width(" recording @q... 0000 fewers lines ")
        fw = self.style().pixelMetric(self.style().PM_DefaultFrameWidth)
        self.setFixedWidth(tw + (2 * fw) + 4)


class WorkerMacro(QThread):
    """Send keyinfo from registers to main thread."""
    sig_focus_vim = Signal()
    sig_send_key_info = Signal(object)

    def __init__(self, parent):
        super().__init__(parent)
        self.key_info_list = []
        self.num_iteration = 0

    def set_key_infos(self, key_infos, num):
        """Set key infos of registers."""
        self.key_info_list = key_infos.copy()
        self.num_iteration = num

    @coverage_resolve_trace
    def run(self):
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
        self.msg_label = VimMsgLabel('', main)

        self.vim_status = VimStatus(editor_widget, main, self.msg_label)
        self.vim_status.change_label.connect(self.status_label.change_state)

        self.vim_shortcut = VimShortcut(self.main,
                                        self.vim_status)

        self.commandline = VimLineEdit(self, self.vim_status,
                                       self.vim_shortcut)
        self.commandline.textChanged.connect(self.on_text_changed)

        self.vim_status.cmd_line = self.commandline
        self.vim_shortcut.cmd_line = self.commandline

        self.executor_normal_cmd = ExecutorNormalCmd(self.vim_status)
        self.executor_visual_cmd = ExecutorVisualCmd(self.vim_status)
        self.executor_vline_cmd = ExecutorVlineCmd(self.vim_status)
        self.executors = {VimState.NORMAL: self.executor_normal_cmd,
                          VimState.VISUAL: self.executor_visual_cmd,
                          VimState.VLINE: self.executor_vline_cmd}

        # leader key
        self.executor_leader_key = ExecutorLeaderKey(self.vim_status)
        self.leader_key = ' '
        self.set_leader_key()

        # macro
        self.worker_macro = WorkerMacro(main)
        self.worker_macro.sig_send_key_info.connect(
            self.send_key_event)
        self.worker_macro.sig_focus_vim.connect(
            self.commandline.setFocus)

    @Slot(object)
    def send_key_event(self, key_info):
        event = key_info.to_event()
        if key_info.identifier == 0:
            self.commandline.keyPressEvent(event)
        else:
            editor = self.vim_status.get_editor()
            editor.keyPressEvent(event)

    def set_leader_key(self):
        """Set leader key from CONF."""
        leader_key = CONF.get(CONF_SECTION, 'leader_key')
        leader_key2 = KEYCODE2STR.get(
                QKeySequence.fromString(leader_key)[0], None)
        if leader_key2:
            leader_key = leader_key2
        self.leader_key = leader_key

    def on_text_changed(self, txt):
        """Send input command to executor."""
        if not txt:
            return

        executor = self.executors[self.vim_status.vim_state]
        if self.vim_status.sub_mode:
            executor = self.vim_status.sub_mode
        elif txt == self.leader_key:
            self.vim_status.sub_mode = self.executor_leader_key
            self.commandline.clear()
            return

        if executor(txt):
            self.commandline.clear()

        if self.vim_status.manager_macro.reg_name_for_execute:
            mm = self.vim_status.manager_macro
            ch = mm.reg_name_for_execute
            self.worker_macro.set_key_infos(
                mm.registers[ch], mm.num_execute)
            self.worker_macro.start()
            mm.set_info_for_execute("", 0)
