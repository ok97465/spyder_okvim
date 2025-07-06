# -*- coding: utf-8 -*-
"""Executor for normal mode commands.

This module implements :class:`ExecutorNormalCmd`, which interprets keystrokes
when the editor is in *normal* mode.  Commands are dispatched to helper classes
for motion and editing actions.  The executor can also switch into various
submodes such as search or register selection.
"""

# Standard Libraries
import re

# Third Party Libraries
from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QKeyEvent, QTextCursor
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.executor.decorators import submode
from spyder_okvim.executor.executor_base import (
    FUNC_INFO,
    RETURN_EXECUTOR_METHOD_INFO,
    ExecutorBase,
)
from spyder_okvim.executor.executor_colon import ExecutorColon
from spyder_okvim.executor.executor_easymotion import ExecutorEasymotion
from spyder_okvim.executor.executor_sub import (
    ExecutorSearch,
    ExecutorSubCmd_alnum,
    ExecutorSubCmd_closesquarebracket,
    ExecutorSubCmd_closebrace,
    ExecutorSubCmd_f_t,
    ExecutorSubCmd_g,
    ExecutorSubCmd_opensquarebracket,
    ExecutorSubCmd_openbrace,
    ExecutorSubCmd_r,
    ExecutorSubCmd_register,
    ExecutorSubCmd_z,
    ExecutorSubCmd_Z,
    ExecutorSubCmdSneak,
    ExecutorSubMotion,
    ExecutorSubMotion_c,
    ExecutorSubMotion_d,
    ExecutorSubMotion_y,
)
from spyder_okvim.executor.mixins import MovementMixin
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.utils.motion import MotionInfo, MotionType


class ExecutorNormalCmd(MovementMixin, ExecutorBase):
    """Executor for normal mode."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        # MovementMixin hooks
        self.move_cursor = self.vim_status.cursor.set_cursor_pos
        self.move_cursor_no_end = self.vim_status.cursor.set_cursor_pos_without_end

        cmds = (
            "aAiIvVhHjpPyJkKlLMoOruwWbBegGsSxdcDCnN^$~:%fFtT\"`'m;,.zZ/<>{} \b\rq@\[\]*#"
        )
        cmds = "".join(re.escape(c) for c in cmds)
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.apply_motion_info_in_normal = (
            self.vim_status.cursor.apply_motion_info_in_normal
        )
        self.apply_motion_info_in_yank = (
            self.vim_status.cursor.apply_motion_info_in_yank
        )
        self.executor_colon = ExecutorColon(vim_status)

        self.executor_sub_g = ExecutorSubCmd_g(vim_status)
        self.executor_sub_f_t = ExecutorSubCmd_f_t(vim_status)
        self.executor_sub_r = ExecutorSubCmd_r(vim_status)
        self.executor_sub_z = ExecutorSubCmd_z(vim_status)
        self.executor_sub_Z = ExecutorSubCmd_Z(vim_status)
        self.executor_sub_motion = ExecutorSubMotion(vim_status)
        self.executor_sub_motion_c = ExecutorSubMotion_c(vim_status)
        self.executor_sub_motion_d = ExecutorSubMotion_d(vim_status)
        self.executor_sub_motion_y = ExecutorSubMotion_y(vim_status)
        self.executor_sub_register = ExecutorSubCmd_register(vim_status)
        self.executor_sub_search = ExecutorSearch(vim_status)
        self.executor_sub_alnum = ExecutorSubCmd_alnum(vim_status)
        self.executor_sub_easymotion = ExecutorEasymotion(vim_status)
        self.executor_sub_sneak = ExecutorSubCmdSneak(vim_status)
        self.executor_sub_opensquarebracekt = ExecutorSubCmd_opensquarebracket(
            vim_status
        )
        self.executor_sub_closesquarebracekt = ExecutorSubCmd_closesquarebracket(
            vim_status
        )
        self.executor_sub_openbrace = ExecutorSubCmd_openbrace(vim_status)
        self.executor_sub_closebrace = ExecutorSubCmd_closebrace(vim_status)

    def a(self, num=1, num_str=""):
        """Append text after the cursor."""
        self.vim_status.update_dot_cmd(connect_editor=True)

        cursor = self.get_cursor()
        if not (cursor.atBlockEnd() and cursor.atBlockStart()):
            cursor.movePosition(QTextCursor.Right)
            self.set_cursor(cursor)
        self.get_editor().setFocus()

    def A(self, num=1, num_str=""):
        """Append text at the end of the line."""
        self.vim_status.update_dot_cmd(connect_editor=True)

        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.EndOfLine)
        self.set_cursor(cursor)
        self.get_editor().setFocus()

    def i(self, num=1, num_str=""):
        """Insert text before the cursor."""
        self.vim_status.update_dot_cmd(connect_editor=True)
        self.get_editor().setFocus()

    def I(self, num=1, num_str=""):
        """Insert text before the first non-blank in the line."""
        self.vim_status.update_dot_cmd(connect_editor=True)

        motion_info = self.helper_motion.caret(num=num)

        cursor = self.get_cursor()
        cursor.setPosition(motion_info.cursor_pos)
        self.set_cursor(cursor)

        self.get_editor().setFocus()

    def v(self, num=1, num_str=""):
        """Start visual mode per character."""
        self.vim_status.to_visual_char()

    def V(self, num=1, num_str=""):
        """Start visual mode per line."""
        self.vim_status.to_visual_line()

    def J(self, num=1, num_str=""):
        """Join lines, with a minimum of two lines."""
        cursor = self.get_cursor()

        if num > 1:
            num -= 1

        block_no_start = cursor.blockNumber()
        block_no_end = cursor.blockNumber() + num
        cursor_pos_start = cursor.position()

        self.helper_action.join_lines(cursor_pos_start, block_no_start, block_no_end)

    def o(self, num=1, num_str=""):
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

    def O(self, num=1, num_str=""):
        """Begin a new line above the cursor and insert text."""
        editor = self.get_editor()
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.insertText("\n")
        cursor.movePosition(QTextCursor.Up)
        editor.setTextCursor(cursor)
        editor.setFocus()

        self.vim_status.update_dot_cmd(connect_editor=True)

    def K(self, num=1, num_str=""):
        """Show the help for the keyword under the cursor."""
        self.get_editorstack().inspect_current_object()
        # self.vim_status.set_focus_to_vim_after_delay(500)

    def u(self, num=1, num_str=""):
        """Undo changes."""
        editor = self.get_editor()
        n_block_old = editor.blockCount()

        for _ in range(num):
            editor.undo()
        cursor = editor.textCursor()
        pos = cursor.position()
        if cursor.atBlockEnd() and not cursor.atBlockStart():
            cursor.movePosition(QTextCursor.Left)
            pos = cursor.position()

        n_block_new = editor.blockCount()
        if n_block_new != n_block_old:
            if n_block_new > n_block_old:
                self.vim_status.set_message(f"{n_block_new - n_block_old} more lines")
            else:
                self.vim_status.set_message(f"{n_block_old - n_block_new} fewer lines")
        else:
            self.vim_status.set_message(f"{num} changes")

        self.set_cursor_pos(pos)

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_normal, True)])
    def g(self, num=1, num_str=""):
        """Start g submode."""
        return self.executor_sub_g

    def G(self, num=1, num_str=""):
        """Move to the line."""
        self.vim_status.push_jump()
        motion_info = self.helper_motion.G(num=num, num_str=num_str)

        self.set_cursor_pos(motion_info.cursor_pos)
        self.vim_status.push_jump()

    def tilde(self, num=1, num_str=""):
        """Switch case of the character under the cursor.

        Move the cursor to the right.
        """
        motion_info = self.helper_motion.l(num, num_str=num_str)

        self.helper_action.handle_case(motion_info, "swap")
        self.set_cursor_pos(motion_info.cursor_pos)

        cursor = self.get_cursor()
        if cursor.atBlockEnd() and not cursor.atBlockStart():
            self.h(1)

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_normal, True)])
    def f(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        return self.executor_sub_f_t

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_normal, True)])
    def F(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        return self.executor_sub_f_t

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_normal, True)])
    def t(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        return self.executor_sub_f_t

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_normal, True)])
    def T(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        return self.executor_sub_f_t

    def r(self, num=1, num_str=""):
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

    def dot(self, num=1, num_str=""):
        """Run previous change."""
        # avoid to execute . command twice.
        self.vim_status.manager_macro.remove_last_key(".")
        cmd_str = self.vim_status.dot_cmd.to_cmd_string(num, num_str)

        if not cmd_str:
            return

        cmd_line = self.vim_status.cmd_line
        self.vim_status.running_dot_cmd = True
        cmd_line.clear()
        for ch in cmd_str:
            cmd_line.setText(cmd_line.text() + ch)

        for key_info in self.vim_status.dot_cmd.key_list_to_cmd_line:
            event = key_info.to_event()
            cmd_line.keyPressEvent(event)

        editor = self.get_editor()
        for key_info in self.vim_status.dot_cmd.key_list_from_editor:
            event = key_info.to_event()
            editor.keyPressEvent(event)

        self.vim_status.running_dot_cmd = False

        self.vim_status.set_focus_to_vim()

        cursor_pos = self.get_cursor().position()
        self.vim_status.cursor.set_cursor_pos_without_end(cursor_pos)

    def z(self, num=1, num_str=""):
        """Start z submode."""
        executor_sub = self.executor_sub_z

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred([])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def Z(self, num=1, num_str=""):
        """Start Z submode."""
        executor_sub = self.executor_sub_Z

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred([])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def greater(self, num=1, num_str=""):
        """Shift lines rightwards."""
        executor_sub = self.executor_sub_motion

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.helper_action.indent, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def less(self, num=1, num_str=""):
        """Shift lines leftwards."""
        executor_sub = self.executor_sub_motion

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.helper_action.unindent, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def quote(self, num=1, num_str=""):
        """Set the name of register."""
        executor_sub = self.executor_sub_register

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred([])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def p(self, num=1, num_str=""):
        """Put the text from register after the cursor."""
        self.helper_action.paste_in_normal(num, is_lower=True)

    def P(self, num=1, num_str=""):
        """Put the text from register after the cursor."""
        self.helper_action.paste_in_normal(num, is_lower=False)

    def y(self, num=1, num_str=""):
        """Yank {motion} text into register."""
        executor_sub = self.executor_sub_motion_y

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [
                FUNC_INFO(lambda x: self.helper_action.yank(x, is_explicit=True), True),
                FUNC_INFO(self.apply_motion_info_in_yank, True),
            ]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def s(self, num=1, num_str=""):
        """Delete characters and start insert."""
        use_sneak = CONF.get(CONF_SECTION, "use_sneak")
        if use_sneak:
            executor_sub = self.executor_sub_sneak

            self.set_parent_info_to_submode(executor_sub, num, num_str)

            executor_sub.set_func_list_deferred(
                [
                    FUNC_INFO(self.apply_motion_info_in_normal, True),
                    FUNC_INFO(
                        self.helper_motion.display_another_group_after_sneak, False
                    ),
                ]
            )
            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)
        else:
            motion_info = self.helper_motion.l(num, num_str)
            self.helper_action.yank(motion_info)
            self.helper_action.delete(motion_info, is_insert=True)
            self.get_editor().setFocus()

    def S(self, num=1, num_str=""):
        """Delete characters and start insert."""
        use_sneak = CONF.get(CONF_SECTION, "use_sneak")
        if use_sneak:
            executor_sub = self.executor_sub_sneak

            self.set_parent_info_to_submode(executor_sub, num, num_str)

            executor_sub.set_func_list_deferred(
                [
                    FUNC_INFO(self.apply_motion_info_in_normal, True),
                    FUNC_INFO(
                        self.helper_motion.display_another_group_after_rsneak, False
                    ),
                ]
            )
            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)
        else:
            cursor = self.get_cursor()
            block = cursor.block()
            txt = block.text()
            n_space = len(txt) - len(txt.lstrip())

            motion_info = self.helper_motion.j(num - 1, num_str)
            self.helper_action.yank(motion_info)
            self.helper_action.delete(
                motion_info, is_insert=True, replace_txt=" " * n_space
            )
            self.get_editor().setFocus()

    def x(self, num=1, num_str=""):
        """Delete characters and start insert."""
        cursor_pos = self.get_cursor().position()

        motion_info = self.helper_motion.l(num, num_str)
        self.helper_action.yank(motion_info)
        self.helper_action.delete(motion_info, is_insert=False)

        self.vim_status.cursor.set_cursor_pos_without_end(cursor_pos)

    def D(self, num=1, num_str=""):
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

    def C(self, num=1, num_str=""):
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

    def d(self, num=1, num_str=""):
        """Delete text."""
        executor_sub = self.executor_sub_motion_d

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [
                FUNC_INFO(self.helper_action.yank, True),
                FUNC_INFO(
                    lambda x: self.helper_action.delete(x, is_insert=False), True
                ),
            ]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def c(self, num=1, num_str=""):
        """Delete text and start insert."""
        executor_sub = self.executor_sub_motion_c

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [
                FUNC_INFO(self.helper_action.yank, True),
                FUNC_INFO(lambda x: self.helper_action.delete(x, is_insert=True), True),
                FUNC_INFO(self.get_editor().setFocus, False),
            ]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def slash(self, num=1, num_str=""):
        """Go to the next searched text."""
        self.vim_status.set_message("")
        executor_sub = self.executor_sub_search

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_normal, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, False)

    def n(self, num=1, num_str=""):
        """Go to the next searched text."""
        self.vim_status.push_jump()
        motion_info = self.helper_motion.n(num=num, num_str=num_str)

        self.set_cursor_pos(motion_info.cursor_pos)
        self.vim_status.push_jump()

    def N(self, num=1, num_str=""):
        """Go to the previous searched text."""
        self.vim_status.push_jump()
        motion_info = self.helper_motion.N(num=num, num_str=num_str)

        self.set_cursor_pos(motion_info.cursor_pos)
        self.vim_status.push_jump()

    def m(self, num=1, num_str=""):
        """Set bookmark with given name."""
        executor_sub = self.executor_sub_alnum
        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.vim_status.set_bookmark, True)]
        )
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def apostrophe(self, num=1, num_str=""):
        """Jump to bookmark linewise."""
        executor_sub = self.executor_sub_alnum
        self.set_parent_info_to_submode(executor_sub, num, num_str)

        def run(ch):
            self.vim_status.push_jump()
            if ch.isupper():
                self.vim_status.jump_to_bookmark(ch)
                cursor = self.get_cursor()
                self.vim_status.cursor.set_cursor_pos(cursor.block().position())
            else:
                info = self.helper_motion.apostrophe(ch)
                if info.cursor_pos is not None:
                    self.vim_status.cursor.set_cursor_pos(info.cursor_pos)
            self.vim_status.push_jump()

        executor_sub.set_func_list_deferred([FUNC_INFO(run, True)])
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def backtick(self, num=1, num_str=""):
        """Jump to bookmark charwise."""
        executor_sub = self.executor_sub_alnum
        self.set_parent_info_to_submode(executor_sub, num, num_str)

        def run(ch):
            self.vim_status.push_jump()
            if ch.isupper():
                self.vim_status.jump_to_bookmark(ch)
            else:
                info = self.helper_motion.backtick(ch)
                if info.cursor_pos is not None:
                    self.vim_status.cursor.set_cursor_pos(info.cursor_pos)
            self.vim_status.push_jump()

        executor_sub.set_func_list_deferred([FUNC_INFO(run, True)])
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def q(self, num=1, num_str=""):
        """Record typed characters into register."""
        if self.vim_status.is_recording_macro():
            self.vim_status.stop_recording_macro()
            self.vim_status.set_message("")
        else:
            executor_sub = self.executor_sub_alnum

            self.set_parent_info_to_submode(executor_sub, num, num_str)

            executor_sub.set_func_list_deferred(
                [
                    FUNC_INFO(self.vim_status.start_recording_macro, True),
                    FUNC_INFO(lambda: self.vim_status.set_message(""), False),
                ]
            )

            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def at(self, num=1, num_str=""):
        """Execute contents of register."""
        if self.vim_status.is_recording_macro():
            self.vim_status.manager_macro.remove_last_key("@")
            return

        executor_sub = self.executor_sub_alnum

        manager_macro = self.vim_status.manager_macro
        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            [FUNC_INFO(lambda x: manager_macro.set_info_for_execute(x, num), True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def run_easymotion(self, num=1, num_str=""):
        """Run easymotion."""
        executor_sub = self.executor_sub_easymotion

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_normal, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_normal, True)])
    def opensquarebracket(self, num=1, num_str=""):
        """Start [ submode."""
        executor_sub = self.executor_sub_opensquarebracekt

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        return executor_sub

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_normal, True)])
    def closesquarebracket(self, num=1, num_str=""):
        """Start ] submode."""
        executor_sub = self.executor_sub_closesquarebracekt

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        return executor_sub

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_normal, True)])
    def openbrace(self, num=1, num_str=""):
        """Start { submode."""
        executor_sub = self.executor_sub_openbrace

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        return executor_sub

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_normal, True)])
    def closebrace(self, num=1, num_str=""):
        """Start } submode."""
        executor_sub = self.executor_sub_closebrace

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        return executor_sub

    def asterisk(self, num=1, num_str=""):
        """Search word under cursor forward."""
        motion_info = self.helper_motion.asterisk(num)
        self.apply_motion_info_in_normal(motion_info)

    def sharp(self, num=1, num_str=""):
        """Search word under cursor backward."""
        motion_info = self.helper_motion.sharp(num)
        self.apply_motion_info_in_normal(motion_info)


