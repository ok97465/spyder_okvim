# -*- coding: utf-8 -*-
"""Status of Vim."""
# Standard library imports
from typing import NamedTuple
from collections import defaultdict

# Third party imports
from qtpy.QtWidgets import QTextEdit, QApplication
from qtpy.QtCore import QObject, Signal, QTimer, Slot, Qt
from qtpy.QtGui import QBrush, QColor, QTextCursor, QKeyEvent

# Local imports
from spyder_okvim.utils.helper_motion import MotionInfo, MotionType


KEY_INFO = NamedTuple("KEY_INFO", [('key_code', int),
                                   ('text', str),
                                   ('modifiers', int)])


class VimState:
    """Vim state constants."""

    VISUAL = 0
    VLINE = 1
    NORMAL = 3
    INSERT = 4
    SUBMODE = 5


class FindInfo:
    """f,F,t,T command Info."""

    def __init__(self):
        self.cmd_name: str = None
        self.ch: str = None

    def set(self, cmd_name: str, ch: str):
        """Set infomation of find commmand."""
        self.cmd_name = cmd_name
        self.ch = ch


class InputCmdInfo:
    """Info for input command."""

    def __init__(self):
        self.num_str: str = ""
        self.cmd: str = ""

    def clear(self):
        """Clear."""
        self.num_str = ""
        self.cmd = ""

    def set(self, input_cmd_info):
        """Set the information of input command."""
        self.num_str = input_cmd_info.num_str
        self.cmd = input_cmd_info.cmd


class DotCmdInfo:
    """Dot command info."""

    def __init__(self):
        self.vim_state = None
        self.sel_block_no_start = None
        self.sel_block_no_end = None
        self.sel_col_start = None
        self.sel_col_end = None
        self.num_str: str = ""
        self.cmd: str = ""
        self.cmd_list_insertmode = None
        self.register_name = None
        self.editor_connected = None
        self.key_list_from_editor = []

    def clear_key_list(self):
        """Clear key list from editor."""
        self.key_list_from_editor.clear()

    def cmd2string(self, num, num_str):
        """Convert cmd info to string of vim command."""
        # TODO : apply register name.
        if self.cmd is None:
            return

        cmd_str = ''

        if self.vim_state == VimState.VLINE:
            cmd_str += 'V'
            n_lines = self.sel_block_no_end - self.sel_block_no_start
            if n_lines > 0:
                cmd_str += f'{n_lines}j'
            cmd_str += self.cmd
            return cmd_str

        if self.vim_state == VimState.VISUAL:
            cmd_str += 'v'
            n_lines = self.sel_block_no_end - self.sel_block_no_start
            if n_lines > 0:
                cmd_str += f'{n_lines}j0'

                if self.sel_col_end > 1:
                    cmd_str += f'{self.sel_col_end - 1}l'
            else:
                n = self.sel_col_end - self.sel_col_start - 1
                if n > 0:
                    cmd_str += f'{n}l'
            cmd_str += self.cmd
            return cmd_str

        if num_str:
            return str(num) + self.cmd
        else:
            return self.num_str + self.cmd


class RegisterInfo:
    """Info of register."""

    def __init__(self):
        self.name = ''
        self.content = ''
        self.type = VimState.NORMAL


class SearchInfo:
    """Result of search."""

    def __init__(self, vim_cursor):
        self.color_fg = QBrush(QColor(0, 0, 0))
        self.color_bg = QBrush(QColor(0, 107, 107))
        self.txt_searched = ''
        self.selection_list = []
        self.vim_cursor = vim_cursor

    def get_sel_start_list(self):
        """Get the start position of selection."""
        editor = self.vim_cursor.get_editor()
        cursor = self.vim_cursor.get_cursor()

        tmp = []
        for sel in self.selection_list:
            cursor.setPosition(sel.cursor.selectionStart())
            cursor.setPosition(sel.cursor.selectionEnd(),
                               QTextCursor.KeepAnchor)
            txt_sel = cursor.selectedText()
            if txt_sel == self.txt_searched:
                tmp.append(sel)
        self.selection_list = tmp

        editor.set_extra_selections('vim_search',
                                    [i for i in self.selection_list])
        editor.update_extra_selections()

        return [i.cursor.selectionStart() for i in self.selection_list]


class VimCursor:
    """Manange the cursor in vim."""

    def __init__(self, editor_widget):
        self.editor_widget = editor_widget

        self.vim_cursor = QTextEdit.ExtraSelection()
        self.vim_cursor.format.setForeground(QBrush(QColor(0, 0, 0)))
        self.vim_cursor.format.setBackground(QBrush(QColor(187, 187, 187)))

        self.selection = QTextEdit.ExtraSelection()
        self.selection.format.setForeground(QBrush(QColor(0, 0, 0)))
        self.selection.format.setBackground(QBrush(QColor(147, 147, 147)))

    def get_editor(self):
        """Get the editor focused."""
        editorstack = self.editor_widget.get_current_editorstack()
        return editorstack.get_current_editor()

    def get_editorstack(self):
        """Get the editorstack."""
        return self.editor_widget.get_current_editorstack()

    def get_cursor(self):
        """Get the cursor."""
        return self.get_editor().textCursor()

    def set_cursor(self, cursor):
        """Set the cursor to focused editor."""
        return self.get_editor().setTextCursor(cursor)

    def get_end_position(self):
        """Get the end position of document."""
        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.End)
        return cursor.position()

    def draw_vim_cursor(self):
        """Draw vim cursor."""
        vim_cursor = self.vim_cursor
        editor = self.get_editor()
        vim_cursor.cursor = editor.textCursor()
        vim_cursor.cursor.movePosition(QTextCursor.Right,
                                       QTextCursor.KeepAnchor)
        editor.set_extra_selections('vim_cursor', [vim_cursor])
        editor.update_extra_selections()

    def create_selection(self, start, end):
        """Create selection."""
        end_document = self.get_end_position()
        if end > end_document:
            end = end_document

        sel = self.selection
        sel.cursor = QTextCursor(self.get_editor().document())
        sel.cursor.setPosition(start)
        sel.cursor.setPosition(end, QTextCursor.KeepAnchor)
        self.get_editor().set_extra_selections("vim_selection", [sel])
        self.draw_vim_cursor()

    def set_cursor_pos_in_visual(self, pos_new):
        """Set cursor position and redraw selection in visual mode.

        Parameters
        ----------
        pos_new : int
            position of cursor

        """
        if pos_new is None:
            return
        editor = self.get_editor()
        pos_cur = editor.textCursor().position()

        sel = editor.get_extra_selections("vim_selection")[0]
        start_old = sel.cursor.selectionStart()
        end_old = sel.cursor.selectionEnd()

        start = start_old
        end = end_old

        if abs(start_old - pos_cur) <= abs(end_old - 1 - pos_cur):
            if start_old >= pos_new:
                start = pos_new
            elif end_old > pos_new:
                start = pos_new
            else:
                start = end - 1
                end = pos_new + 1
        else:
            if end_old - 1 <= pos_new:
                end = pos_new + 1
            elif start_old < pos_new:
                end = pos_new + 1
            else:
                end = start_old + 1
                start = pos_new

        end_document = self.get_end_position()
        if end > end_document:
            end = end_document

        sel.cursor.setPosition(start)
        sel.cursor.setPosition(end, QTextCursor.KeepAnchor)
        editor.set_extra_selections("vim_selection", [sel])
        self.set_cursor_pos(pos_new)

    def get_block(self, pos):
        """Get block number of cursor position.

        Returns
        -------
        QTextBlock
            The QTextBlock class provides a container for text fragments.
        int
            Block number.
        """
        cursor = self.get_cursor()
        cursor.setPosition(pos)
        return cursor.block(), cursor.blockNumber()

    def get_block_no_start_in_selection(self):
        """Get start block number of selection."""
        editor = self.get_editor()

        sel = editor.get_extra_selections("vim_selection")
        if not sel:
            return

        sel = sel[0]

        sel_start = sel.cursor.selectionStart()

        _, block_no_start = self.get_block(sel_start)

        return block_no_start

    def get_block_no_end_in_selection(self):
        """Get the last block number of selection."""
        editor = self.get_editor()

        sel = editor.get_extra_selections("vim_selection")
        if not sel:
            return

        sel = sel[0]

        sel_end = sel.cursor.selectionEnd()

        _, block_no_end = self.get_block(sel_end)

        return block_no_end

    def get_pos_start_in_selection(self):
        """Get start position of selection."""
        editor = self.get_editor()

        sel = editor.get_extra_selections("vim_selection")
        if not sel:
            return

        sel = sel[0]

        sel_start = sel.cursor.selectionStart()

        return sel_start

    def get_pos_end_in_selection(self):
        """Get end position of selection."""
        editor = self.get_editor()

        sel = editor.get_extra_selections("vim_selection")
        if not sel:
            return

        sel = sel[0]

        sel_end = sel.cursor.selectionEnd()

        return sel_end

    def set_selection_to_editor_using_vim_selection(self):
        """Set the selection to editor by referring the selection of vim."""
        editor = self.get_editor()
        old_cursor = editor.textCursor()
        sel_start = self.get_pos_start_in_selection()
        sel_end = self.get_pos_end_in_selection()
        if sel_start:
            new_cursor = editor.textCursor()
            new_cursor.setPosition(sel_start, QTextCursor.MoveAnchor)
            new_cursor.setPosition(sel_end, QTextCursor.KeepAnchor)
            editor.setTextCursor(new_cursor)
            return old_cursor

    def set_cursor_pos_in_vline(self, pos_new):
        """Set cursor position and redraw selection in vline mode.

        Parameters
        ----------
        pos_new : int
            position of cursor

        """
        if pos_new is None:
            return
        editor = self.get_editor()
        block_no_cur = editor.textCursor().blockNumber()

        sel = editor.get_extra_selections("vim_selection")[0]
        sel_start = sel.cursor.selectionStart()
        sel_end = sel.cursor.selectionEnd()

        block_start, block_no_start = self.get_block(sel_start)
        block_end, block_no_end = self.get_block(sel_end)
        block_new, block_no_new = self.get_block(pos_new)

        if block_no_start == block_no_cur:
            if block_no_new <= block_no_end:
                block_start = block_new
            else:
                block_start = block_end
                block_end = block_new
        else:
            if block_no_new >= block_no_start:
                block_end = block_new
            else:
                block_end = block_start
                block_start = block_new

        start = block_start.position()
        end = block_end.position() + block_end.length() - 1
        sel.cursor.setPosition(start)
        sel.cursor.setPosition(end, QTextCursor.KeepAnchor)
        editor.set_extra_selections("vim_selection", [sel])
        self.set_cursor_pos(pos_new)

    def set_block_selection_in_visual(self, motion_info: MotionInfo):
        """Set block selection in visual."""
        editor = self.get_editor()
        sel = editor.get_extra_selections("vim_selection")[0]
        sel.cursor.setPosition(motion_info.sel_start)
        sel.cursor.setPosition(motion_info.sel_end, QTextCursor.KeepAnchor)
        editor.set_extra_selections("vim_selection", [sel])
        self.set_cursor_pos(motion_info.sel_end - 1)

    def set_cursor_pos(self, pos):
        """Set position cursor of editor."""
        if pos is None:
            return
        editor = self.get_editor()
        cursor = editor.textCursor()
        cursor.setPosition(pos)
        self.set_cursor(cursor)
        self.draw_vim_cursor()

    def set_cursor_pos_without_end(self, pos):
        """Set position cursor of editor."""
        if pos is None:
            return
        editor = self.get_editor()
        cursor = editor.textCursor()
        cursor.setPosition(pos)
        if cursor.atBlockEnd() and not cursor.atBlockStart():
            cursor.movePosition(QTextCursor.Left)
        self.set_cursor(cursor)
        self.draw_vim_cursor()

    def apply_motion_info_in_normal(self, motion_info: MotionInfo):
        """Apply motion info in normal mode."""
        self.set_cursor_pos(motion_info.cursor_pos)

    def apply_motion_info_in_yank(self, motion_info: MotionInfo):
        """Apply motion info after yank in normal mode."""
        cursor_pos = self.get_cursor().position()
        if motion_info.motion_type == MotionType.BlockWise:
            self.set_cursor_pos(motion_info.sel_start)
        else:
            if motion_info.cursor_pos is None:
                return
            pos = min([cursor_pos, motion_info.cursor_pos])
            self.set_cursor_pos(pos)

    def apply_motion_info_in_visual(self, motion_info: MotionInfo):
        """Apply motion info in visual mode."""
        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def apply_motion_info_in_vline(self, motion_info: MotionInfo):
        """Apply motion info in visual mode."""
        self.set_cursor_pos_in_vline(motion_info.cursor_pos)


class VimStatus(QObject):
    """Status of vim."""

    change_label = Signal(int)

    def __init__(self, editor_widget, main):
        super().__init__()
        self.is_visual_mode = False
        self.vim_state = VimState.NORMAL
        self.editor_widget = editor_widget
        self.cursor: VimCursor = VimCursor(editor_widget)
        self.main = main

        # method mapping
        self.set_cursor = self.cursor.set_cursor
        self.get_cursor = self.cursor.get_cursor
        self.get_editor = self.cursor.get_editor
        self.get_editorstack = self.cursor.get_editorstack
        self.get_block_no_start_in_selection = \
            self.cursor.get_block_no_start_in_selection
        self.get_block_no_end_in_selection = \
            self.cursor.get_block_no_end_in_selection
        self.get_pos_start_in_selection = \
            self.cursor.get_pos_start_in_selection
        self.get_pos_end_in_selection = \
            self.cursor.get_pos_end_in_selection

        self.set_focus_to_cmd_line = None

        self.sub_mode = None

        # command
        self.find_info = FindInfo()
        self.input_cmd = InputCmdInfo()
        self.input_cmd_prev = InputCmdInfo()
        self.dot_cmd = DotCmdInfo()
        self.running_dot_cmd = False

        # register
        self.register_dict = defaultdict(RegisterInfo)

        # config
        self.indent = "    "

        # search
        self.search = SearchInfo(self.cursor)

    def clear_state(self):
        """Clear."""
        self.is_visual_mode = False
        self.vim_state = VimState.NORMAL
        self.get_editor().clear_extra_selections("vim_selection")
        self.get_editor().clear_extra_selections("vim_cursor")

    def is_normal(self):
        """Check that vim state is normal mode."""
        return self.vim_state == VimState.NORMAL

    def to_normal(self):
        """Change vim state to normal mode."""
        self.clear_state()
        cursor = self.get_cursor()
        if cursor.atBlockEnd() and not cursor.atBlockStart():
            pos = cursor.position()
            self.cursor.set_cursor_pos(pos - 1)
        self.change_label.emit(VimState.NORMAL)

    def to_insert(self):
        """Change vim state to insert mode."""
        self.is_visual_mode = False
        self.get_editor().clear_extra_selections("vim_selection")
        self.get_editor().clear_extra_selections("vim_cursor")
        self.change_label.emit(VimState.INSERT)

    def to_visual_char(self):
        """Change vim state to visual mode."""
        self.clear_state()
        self.is_visual_mode = True
        self.vim_state = VimState.VISUAL

        pos = self.get_cursor().position()
        self.cursor.create_selection(pos, pos + 1)

        self.change_label.emit(VimState.VISUAL)

    def to_visual_line(self):
        """Change vim state to vline mode."""
        self.clear_state()
        self.is_visual_mode = True
        self.vim_state = VimState.VLINE

        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.StartOfBlock)

        pos_start = cursor.position()

        cursor.movePosition(QTextCursor.EndOfBlock)
        pos_end = cursor.position()

        self.cursor.create_selection(pos_start, pos_end)

        self.change_label.emit(VimState.VLINE)

    def get_number_of_visible_lines(self):
        """Get the number of visible lines in editor."""
        editor = self.get_editor()
        num_lines = editor.viewport().height() // editor.fontMetrics().height()
        return num_lines

    def set_focus_to_vim(self):
        """Set focus to vim command line."""
        if self.set_focus_to_cmd_line:
            self.set_focus_to_cmd_line()

    def set_focus_to_vim_after_delay(self, delay=300):
        """Set focus to vim command line after delay.

        Spyder is focused after receiving the result of pyls.
        So set_focus_to_vim method is useless.
        """
        def focus():
            self.set_focus_to_vim()
            self.cursor.draw_vim_cursor()
        if self.set_focus_to_cmd_line:
            QTimer.singleShot(delay, focus)

    @Slot(QKeyEvent)
    def rcv_key_from_editor(self, event):
        """Add key event from editor to list."""
        self.dot_cmd.key_list_from_editor.append(
            KEY_INFO(event.key(), event.text(), event.modifiers()))

    def disconnect_from_editor(self):
        """Disconnect from the editor."""
        # disconnect previous connection.
        editor = self.dot_cmd.editor_connected
        if editor:
            editor.sig_key_pressed.disconnect(self.rcv_key_from_editor)
        self.dot_cmd.editor_connected = None

    def update_dot_cmd(self, connect_editor, register_name=None):
        """Update input command info to dot command info."""
        if self.running_dot_cmd is True:
            return
        dot_cmd = self.dot_cmd
        dot_cmd.vim_state = self.vim_state
        dot_cmd.num_str = self.input_cmd.num_str
        dot_cmd.cmd = self.input_cmd.cmd
        dot_cmd.register_name = register_name
        dot_cmd.clear_key_list()
        self.disconnect_from_editor()

        # For receiving key event from codeeditor
        if connect_editor:
            editor = self.get_editor()
            self.dot_cmd.editor_connected = editor
            editor.sig_key_pressed.connect(self.rcv_key_from_editor)

        # Get selection region.
        if self.is_normal():
            return

        sel_start = self.get_pos_start_in_selection()
        sel_end = self.get_pos_end_in_selection()

        block_start, block_no_start = self.cursor.get_block(sel_start)
        block_end, block_no_end = self.cursor.get_block(sel_end)

        dot_cmd.sel_block_no_start = block_no_start
        dot_cmd.sel_block_no_end = block_no_end
        dot_cmd.sel_col_start = sel_start - block_start.position()
        dot_cmd.sel_col_end = sel_end - block_end.position()

    def get_register_name(self):
        """Get register name from previous command."""
        txt = self.input_cmd_prev.cmd

        if len(txt) == 2 and txt[0] == '"':
            return txt[1]
        else:
            return '"'  # default register name

    def set_register(self, name, content, register_type):
        """Set content into register_dict."""
        if name == "+":
            QApplication.clipboard().setText(content)
        else:
            info = self.register_dict[name]
            info.name = name
            info.content = content
            info.type = register_type
            self.register_dict[name] = info

    def get_register(self):
        """Get content from register_dict."""
        name = self.get_register_name()
        if name == '+':
            info = RegisterInfo()
            info.name = '+'
            info.content = QApplication.clipboard().text()
            info.type = VimState.NORMAL
            return info
        else:
            return self.register_dict[name]