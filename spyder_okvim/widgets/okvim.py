# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) Spyder Project Contributors
#
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
# -----------------------------------------------------------------------------
"""OkVim Widget."""
# %% Import
# Third party imports
from qtpy.QtWidgets import QLineEdit, QWidget, QLabel
from qtpy.QtCore import Qt, Slot, Signal, QObject
from qtpy.QtGui import QTextCursor

# Local imports
from spyder_okvim.executor import (ExecutorNormalCmd, ExecutorVisualCmd,
                                   ExecutorVlineCmd)
from spyder_okvim.utils.vim_status import (VimStatus, VimState, InputCmdInfo,
                                           KeyInfo)


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

    def pg_half_down(self):
        """Scroll window downward."""
        scroll_lines = self.vim_status.get_number_of_visible_lines() // 2
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

            try:
                txt = self.cmd_line.text()
                num = 1 if not txt else int(txt)
            except ValueError:
                self.cmd_line.esc_pressed()
                return

            cursor = self.get_editor().textCursor()
            cursor.setPosition(pos_start)
            cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
            cursor.insertText(str(val + num))
            self.signal_cmd.emit("h")

            # Update dot cmd
            cmd_info = InputCmdInfo(str(num), "")
            self.vim_status.input_cmd.set(cmd_info)
            key_info = KeyInfo(Qt.Key_A, '', Qt.ControlModifier)
            self.vim_status.update_dot_cmd(
                    False, key_list_to_cmd_line=[key_info])

    def subtract_num(self):
        """Subtract to the number at the cursor."""
        val, pos_start, pos_end = self._extract_number()

        if val is not None:
            if self.vim_status.sub_mode:
                self.cmd_line.esc_pressed()
                return

            try:
                txt = self.cmd_line.text()
                num = 1 if not txt else int(txt)
            except ValueError:
                self.cmd_line.esc_pressed()
                return

            cursor = self.get_editor().textCursor()
            cursor.setPosition(pos_start)
            cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
            cursor.insertText(str(val - num))
            self.signal_cmd.emit("h")

            # Update dot cmd
            cmd_info = InputCmdInfo(str(num), "")
            self.vim_status.input_cmd.set(cmd_info)
            key_info = KeyInfo(Qt.Key_X, '', Qt.ControlModifier)
            self.vim_status.update_dot_cmd(
                    False, key_list_to_cmd_line=[key_info])

    def redo(self):
        """ Redo [count changes which were undone. """
        if self.vim_status.sub_mode:
            self.cmd_line.esc_pressed()
            return

        if not self.vim_status.is_normal():
            return

        try:
            txt = self.cmd_line.text()
            num = 1 if not txt else int(txt)
        except ValueError:
            self.cmd_line.esc_pressed()
            return

        editor = self.get_editor()
        for _ in range(num):
            editor.redo()

        self.cmd_line.esc_pressed()

    def open_symbols_dlg(self):
        """Open switcher for symbol."""
        self.main.open_switcher(symbol=True)


class VimStateLabel(QLabel):
    """Display state of vim."""

    def __init__(self, parent):
        super().__init__(parent)
        self.change_state(VimState.INSERT)

    @Slot(int)
    def change_state(self, state):
        """Display the state of vim."""
        self.setStyleSheet("QLabel { color: white, padding:2px }")
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

        # Todo: Move setting shortcut to config file.
        vim_shortcut.signal_cmd.connect(self.setText)
        self.dispatcher = {Qt.Key_A: vim_shortcut.add_num,
                           Qt.Key_X: vim_shortcut.subtract_num,
                           Qt.Key_S: vim_shortcut.open_symbols_dlg,
                           Qt.Key_D: vim_shortcut.pg_half_down,
                           Qt.Key_U: vim_shortcut.pg_half_up,
                           Qt.Key_R: vim_shortcut.redo}

    def to_normal(self):
        """Convert the state of vim to normal mode."""
        self.clear()
        self.vim_widget.vim_status.to_normal()
        self.vim_widget.vim_status.cursor.draw_vim_cursor()

    def keyPressEvent(self, e):
        """Override Qt method."""
        key = e.key()
        pressed_ctrl = e.modifiers() == Qt.ControlModifier
        if key == Qt.Key_Escape:
            self.esc_pressed()
        elif key in [Qt.Key_Return, Qt.Key_Enter]:
            self.setText(self.text() + '\r')
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

    def focusOutEvent(self, event):
        """Override Qt method."""
        super().focusInEvent(event)
        self.clear()
        self.vim_widget.vim_status.to_insert()


class VimWidget(QWidget):
    """Vim widget."""

    def __init__(self, editor_widget, main):
        super().__init__(main)
        self.editor_widget = editor_widget
        self.main = main
        self.status_label = VimStateLabel(main)

        self.vim_status = VimStatus(editor_widget, main)
        self.vim_status.change_label.connect(self.status_label.change_state)

        self.vim_shortcut = VimShortcut(self.main,
                                        self.vim_status)

        self.commandline = VimLineEdit(self, self.vim_status,
                                       self.vim_shortcut)
        self.commandline.textChanged.connect(self.on_text_changed)

        self.vim_status.set_focus_to_cmd_line = self.commandline.setFocus
        self.vim_shortcut.cmd_line = self.commandline

        self.executor_normal_cmd = ExecutorNormalCmd(self.vim_status,
                                                     self.commandline)
        self.executor_visual_cmd = ExecutorVisualCmd(self.vim_status)
        self.executor_vline_cmd = ExecutorVlineCmd(self.vim_status)
        self.executors = {VimState.NORMAL: self.executor_normal_cmd,
                          VimState.VISUAL: self.executor_visual_cmd,
                          VimState.VLINE: self.executor_vline_cmd}

    def on_text_changed(self, txt):
        """Send input command to executor."""
        if not txt:
            return

        executor = self.executors[self.vim_status.vim_state]
        if self.vim_status.sub_mode:
            executor = self.vim_status.sub_mode
        if executor(txt):
            self.commandline.clear()
