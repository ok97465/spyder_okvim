# -*- coding: utf-8 -*-
"""."""
# %% Import
# Standard library imports
import re

# Third party imports
from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QKeyEvent, QTextCursor

# Local imports
from spyder_okvim.executor.executor_base import (
    FUNC_INFO, RETURN_EXECUTOR_METHOD_INFO, ExecutorBase,)
from spyder_okvim.utils.helper_motion import MotionInfo, MotionType
from spyder_okvim.executor.executor_sub import (
    ExecutorSubColon, ExecutorSubCmd_f_t, ExecutorSubCmd_g, ExecutorSubCmd_r,
    ExecutorSubCmd_Z, ExecutorSubMotion, ExecutorSubSpace, ExecutorSearch,
    ExecutorSubMotion_c, ExecutorSubMotion_d, ExecutorSubCmd_register)


class ExecutorNormalCmd(ExecutorBase):
    """Executor for normal mode."""

    def __init__(self, vim_status, cmd_line):
        super().__init__(vim_status)

        self.cmd_line = cmd_line

        cmds = 'aAiIvVhHjpPyJkKlLMoOruwWbegGsSxdcDCnN^$~:%fFtT";,.Z/<> '
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.apply_motion_info_in_normal = \
            self.vim_status.cursor.apply_motion_info_in_normal
        self.apply_motion_info_in_yank = \
            self.vim_status.cursor.apply_motion_info_in_yank
        self.executor_colon = ExecutorSubColon(vim_status)

        self.executor_sub_g = ExecutorSubCmd_g(vim_status)
        self.executor_sub_f_t = ExecutorSubCmd_f_t(vim_status)
        self.executor_sub_r = ExecutorSubCmd_r(vim_status)
        self.executor_sub_Z = ExecutorSubCmd_Z(vim_status)
        self.executor_sub_motion = ExecutorSubMotion(vim_status)
        self.executor_sub_motion_c = ExecutorSubMotion_c(vim_status)
        self.executor_sub_motion_d = ExecutorSubMotion_d(vim_status)
        self.executor_sub_space = ExecutorSubSpace(vim_status)
        self.executor_sub_register = ExecutorSubCmd_register(vim_status)
        self.executor_sub_search = ExecutorSearch(vim_status)

    def colon(self, num=1, num_str=''):
        """Execute submode for ;."""
        return RETURN_EXECUTOR_METHOD_INFO(self.executor_colon, False)

    def zero(self, num=1, num_str=''):
        """Go to the start of the current line."""
        motion_info = self.helper_motion.zero()

        self.set_cursor_pos(motion_info.cursor_pos)

    def a(self, num=1, num_str=''):
        """Append text after the cursor."""
        self.vim_status.update_dot_cmd(connect_editor=True)

        cursor = self.get_cursor()
        if not (cursor.atBlockEnd() and cursor.atBlockStart()):
            cursor.movePosition(QTextCursor.Right)
            self.set_cursor(cursor)
        self.get_editor().setFocus()

    def A(self, num=1, num_str=''):
        """Append text at the end of the line."""
        self.vim_status.update_dot_cmd(connect_editor=True)

        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.EndOfLine)
        self.set_cursor(cursor)
        self.get_editor().setFocus()

    def i(self, num=1, num_str=''):
        """Insert text before the cursor."""
        self.vim_status.update_dot_cmd(connect_editor=True)
        self.get_editor().setFocus()

    def I(self, num=1, num_str=''):
        """Insert text before the first non-blank in the line."""
        self.vim_status.update_dot_cmd(connect_editor=True)

        motion_info = self.helper_motion.caret(num=num)

        cursor = self.get_cursor()
        cursor.setPosition(motion_info.cursor_pos)
        self.set_cursor(cursor)

        self.get_editor().setFocus()

    def v(self, num=1, num_str=''):
        """Start visual mode per character."""
        self.vim_status.to_visual_char()

    def V(self, num=1, num_str=''):
        """Start visual mode per line."""
        self.vim_status.to_visual_line()

    def l(self, num=1, num_str=''):
        """Move cursor to right."""
        motion_info = self.helper_motion.l(num=num)

        self.vim_status.cursor.set_cursor_pos_without_end(
            motion_info.cursor_pos)

    def h(self, num=1, num_str=''):
        """Move cursor to left."""
        motion_info = self.helper_motion.h(num=num)

        self.set_cursor_pos(motion_info.cursor_pos)

    def k(self, num=1, num_str=''):
        """Move cursor to up."""
        motion_info = self.helper_motion.k(num=num)

        self.set_cursor_pos(motion_info.cursor_pos)

    def j(self, num=1, num_str=''):
        """Move cursor to down."""
        motion_info = self.helper_motion.j(num=num)

        self.set_cursor_pos(motion_info.cursor_pos)

    def H(self, num=1, num_str=''):
        """Move cursor to the top of the page."""
        motion_info = self.helper_motion.H(num=num)

        self.set_cursor_pos(motion_info.cursor_pos)

    def M(self, num=1, num_str=''):
        """Move cursor to the middle of the page."""
        motion_info = self.helper_motion.M(num=num)

        self.set_cursor_pos(motion_info.cursor_pos)

    def L(self, num=1, num_str=''):
        """Move cursor to the bottom of the page."""
        motion_info = self.helper_motion.L(num=num)

        self.set_cursor_pos(motion_info.cursor_pos)

    def J(self, num=1, num_str=''):
        """Join lines, with a minimum of two lines."""
        cursor = self.get_cursor()

        if num > 1:
            num -= 1

        block_no_start = cursor.blockNumber()
        block_no_end = cursor.blockNumber() + num
        cursor_pos_start = cursor.position()

        self.helper_action.join_lines(cursor_pos_start,
                                      block_no_start, block_no_end)

    def caret(self, num=1, num_str=''):
        """Move cursor to the first non-blank character of the line."""
        motion_info = self.helper_motion.caret(num=num)

        self.set_cursor_pos(motion_info.cursor_pos)

    def dollar(self, num=1, num_str=''):
        """Move cursor to the end of the line."""
        motion_info = self.helper_motion.dollar(num=num)

        self.vim_status.cursor.set_cursor_pos_without_end(
            motion_info.cursor_pos)

    def o(self, num=1, num_str=''):
        """Begin a new line below the cursor and insert text."""
        editor = self.get_editor()
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.EndOfLine)
        editor.setTextCursor(cursor)
        editor.setFocus()

        # Send the keyevent to editor for using autoindent of editor.
        new_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
        editor.keyPressEvent(new_event)

        self.vim_status.update_dot_cmd(connect_editor=True)

    def O(self, num=1, num_str=''):
        """Begin a new line above the cursor and insert text."""
        editor = self.get_editor()
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.insertText("\n")
        cursor.movePosition(QTextCursor.Up)
        editor.setTextCursor(cursor)
        editor.setFocus()

        self.vim_status.update_dot_cmd(connect_editor=True)

    def K(self, num=1, num_str=''):
        """Show the help for the keyword under the cursor."""
        self.get_editorstack().inspect_current_object()
        self.vim_status.set_focus_to_vim_after_delay(500)

    def u(self, num=1, num_str=''):
        """Undo changes."""
        editor = self.get_editor()
        for _ in range(num):
            editor.undo()
        cursor = editor.textCursor()
        pos = cursor.position()
        if cursor.atBlockEnd() and not cursor.atBlockStart():
            cursor.movePosition(QTextCursor.Left)
            pos = cursor.position()

        self.set_cursor_pos(pos)

    def w(self, num=1, num_str=''):
        """Move to the next word."""
        motion_info = self.helper_motion.w(num=num)

        self.vim_status.cursor.set_cursor_pos_without_end(
            motion_info.cursor_pos)

    def W(self, num=1, num_str=''):
        """Move to the next WORD."""
        motion_info = self.helper_motion.W(num=num)

        self.vim_status.cursor.set_cursor_pos_without_end(
            motion_info.cursor_pos)

    def b(self, num=1, num_str=''):
        """Move to the previous word."""
        motion_info = self.helper_motion.b(num=num)

        self.set_cursor_pos(motion_info.cursor_pos)

    def e(self, num=1, num_str=''):
        """Move to the end of word."""
        motion_info = self.helper_motion.e(num=num)

        self.set_cursor_pos(motion_info.cursor_pos)

    def g(self, num=1, num_str=''):
        """Start g submode."""
        executor_sub = self.executor_sub_g

        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_normal, True)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def G(self, num=1, num_str=''):
        """Move to the line."""
        motion_info = self.helper_motion.G(num=num,
                                           num_str=num_str)

        self.set_cursor_pos(motion_info.cursor_pos)

    def tilde(self, num=1, num_str=''):
        """Switch case of the character under the cursor.

        Move the cursor to the right.
        """
        motion_info = self.helper_motion.l(num, num_str=num_str)

        self.helper_action.handle_case(motion_info, 'swap')
        self.set_cursor_pos(motion_info.cursor_pos)

        cursor = self.get_cursor()
        if cursor.atBlockEnd() and not cursor.atBlockStart():
            self.h(1)

    def percent(self, num=1, num_str=''):
        """Go to matching bracket."""
        motion_info = self.helper_motion.percent(num=num,
                                                 num_str=num_str)

        self.set_cursor_pos(motion_info.cursor_pos)

    def f(self, num=1, num_str=''):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_normal, True)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def F(self, num=1, num_str=''):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_normal, True)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def t(self, num=1, num_str=''):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_normal, True)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def T(self, num=1, num_str=''):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_normal, True)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def semicolon(self, num=1, num_str=''):
        """Repeat latest f, t, f, T."""
        motion_info = self.helper_motion.semicolon(num=num,
                                                   num_str=num_str)

        self.set_cursor_pos(motion_info.cursor_pos)

    def comma(self, num=1, num_str=''):
        """Repeat latest f, t, f, T in opposite direction."""
        motion_info = self.helper_motion.comma(num=num,
                                               num_str=num_str)

        self.set_cursor_pos(motion_info.cursor_pos)

    def r(self, num=1, num_str=''):
        """Replace the ch under the cursor with input."""
        cursor = self.get_cursor()
        pos_start = cursor.position()
        cursor.movePosition(QTextCursor.EndOfBlock)
        pos_block_end = cursor.position()
        if pos_block_end - pos_start < num:
            pos_end = pos_start
        else:
            pos_end = pos_start + num

        executor_sub = self.executor_sub_r
        executor_sub.pos_start = pos_start
        executor_sub.pos_end = pos_end

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def dot(self, num=1, num_str=''):
        """Run previous change."""
        cmd_str = self.vim_status.dot_cmd.cmd2string(num, num_str)

        if not cmd_str:
            return

        self.vim_status.running_dot_cmd = True
        self.cmd_line.clear()
        for ch in cmd_str:
            self.cmd_line.setText(self.cmd_line.text() + ch)

        for key_info in self.vim_status.dot_cmd.key_list_to_cmd_line:
            event = key_info.to_event()
            self.cmd_line.keyPressEvent(event)

        editor = self.get_editor()
        for key_info in self.vim_status.dot_cmd.key_list_from_editor:
            event = key_info.to_event()
            editor.keyPressEvent(event)

        self.vim_status.running_dot_cmd = False

        self.vim_status.set_focus_to_vim()

        cursor_pos = self.get_cursor().position()
        self.vim_status.cursor.set_cursor_pos_without_end(cursor_pos)

    def Z(self, num=1, num_str=''):
        """Start Z submode."""
        executor_sub = self.executor_sub_Z

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred([])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def greater(self, num=1, num_str=''):
        """Shift lines rightwards."""
        executor_sub = self.executor_sub_motion

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.helper_action.indent, True)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def less(self, num=1, num_str=''):
        """Shift lines leftwards."""
        executor_sub = self.executor_sub_motion

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.helper_action.unindent, True)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def space(self, num=1, num_str=''):
        """Call submode of space."""
        executor_sub = self.executor_sub_space

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred([])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def quote(self, num=1, num_str=''):
        """Set the name of register."""
        executor_sub = self.executor_sub_register

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred([])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def p(self, num=1, num_str=''):
        """Put the text from register after the cursor."""
        self.helper_action.paste_in_normal(num, is_lower=True)

    def P(self, num=1, num_str=''):
        """Put the text from register after the cursor."""
        self.helper_action.paste_in_normal(num, is_lower=False)

    def y(self, num=1, num_str=''):
        """Yank {motion} text into register."""
        executor_sub = self.executor_sub_motion

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(lambda x:self.helper_action.yank(x, is_explicit=True),
                       True),
             FUNC_INFO(self.apply_motion_info_in_yank, True)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def s(self, num=1, num_str=''):
        """Delete characters and start insert."""
        motion_info = self.helper_motion.l(num, num_str)
        self.helper_action.yank(motion_info)
        self.helper_action.delete(motion_info, is_insert=True)
        self.get_editor().setFocus()

    def S(self, num=1, num_str=''):
        """Delete characters and start insert."""
        cursor = self.get_cursor()
        block = cursor.block()
        txt = block.text()
        n_space = len(txt) - len(txt.lstrip())

        motion_info = self.helper_motion.j(num - 1, num_str)
        self.helper_action.yank(motion_info)
        self.helper_action.delete(motion_info, is_insert=True,
                                  replace_txt=' ' * n_space)
        self.get_editor().setFocus()

    def x(self, num=1, num_str=''):
        """Delete characters and start insert."""
        cursor_pos = self.get_cursor().position()

        motion_info = self.helper_motion.l(num, num_str)
        self.helper_action.yank(motion_info)
        self.helper_action.delete(motion_info, is_insert=False)

        self.vim_status.cursor.set_cursor_pos_without_end(cursor_pos)

    def D(self, num=1, num_str=''):
        """Delete the characters under the cursor until the end of the line.

        If count is greater than 1, This command deletes [count]-1 more lines.
        (not linewise)
        """
        editor = self.get_editor()
        n_block = editor.blockCount()
        block_no_start = self.get_cursor().blockNumber()
        block_no_end = min([n_block - 1, block_no_start + num - 1])
        block = editor.document().findBlockByNumber(block_no_end)

        motion_info = MotionInfo()
        motion_info.cursor_pos = block.position() + block.length() - 1
        motion_info.motion_type = MotionType.CharWise
        sel_start, sel_end = self.helper_action.yank(motion_info)
        self.helper_action.delete(motion_info, is_insert=False)

        self.vim_status.cursor.set_cursor_pos_without_end(sel_start)

    def C(self, num=1, num_str=''):
        """Execute D command and start insert mode."""
        editor = self.get_editor()
        n_block = editor.blockCount()
        block_no_start = self.get_cursor().blockNumber()
        block_no_end = min([n_block - 1, block_no_start + num - 1])
        block = editor.document().findBlockByNumber(block_no_end)

        motion_info = MotionInfo()
        motion_info.cursor_pos = block.position() + block.length() - 1
        motion_info.motion_type = MotionType.CharWise
        sel_start, sel_end = self.helper_action.yank(motion_info)
        self.helper_action.delete(motion_info, is_insert=True)

        self.vim_status.cursor.set_cursor_pos(sel_start)
        self.get_editor().setFocus()

    def d(self, num=1, num_str=''):
        """Delete text."""
        executor_sub = self.executor_sub_motion_d

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.helper_action.yank, True),
             FUNC_INFO(lambda x: self.helper_action.delete(x, is_insert=False),
                       True)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def c(self, num=1, num_str=''):
        """Delete text and start insert."""
        executor_sub = self.executor_sub_motion_c

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.helper_action.yank, True),
             FUNC_INFO(lambda x: self.helper_action.delete(x, is_insert=True),
                       True),
             FUNC_INFO(self.get_editor().setFocus, False)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def slash(self, num=1, num_str=''):
        """Go to the next searched text."""
        executor_sub = self.executor_sub_search

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred([
            FUNC_INFO(self.apply_motion_info_in_normal, True)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, False)

    def n(self, num=1, num_str=''):
        """Go to the next searched text."""
        motion_info = self.helper_motion.n(num=num, num_str=num_str)

        self.set_cursor_pos(motion_info.cursor_pos)

    def N(self, num=1, num_str=''):
        """Go to the previous searched text."""
        motion_info = self.helper_motion.N(num=num, num_str=num_str)

        self.set_cursor_pos(motion_info.cursor_pos)
