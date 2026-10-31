# -*- coding: utf-8 -*-
"""Executor for normal mode commands.

This module implements :class:`NormalModeExecutor`, which interprets keystrokes
when the editor is in *normal* mode.  Commands are dispatched to helper classes
for motion and editing actions.  The executor can also switch into various
submodes such as search or register selection.
"""

# Standard Libraries
import re

# Third Party Libraries
from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QKeyEvent, QTextCursor

# Project Libraries
from spyder_okvim.executor.decorators import submode
from spyder_okvim.executor.executor_base import (
    DeferredAction,
    ExecutorBase,
    ExecutorTransition,
)
from spyder_okvim.executor.executor_colon import ExecutorColon
from spyder_okvim.executor.mixins import MovementMixin
from spyder_okvim.executor.operators import (
    ChangeOperatorExecutor,
    DeleteOperatorExecutor,
    OperatorMotionExecutor,
    YankOperatorExecutor,
)
from spyder_okvim.executor.prefixes import (
    FileExitExecutor,
    ModeSubmodes,
    ViewportPrefixExecutor,
)
from spyder_okvim.utils.motion import MotionInfo, MotionType


class NormalModeExecutor(MovementMixin, ExecutorBase):
    """Interpret normal-mode keys and delegate motions, edits and host actions."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        # MovementMixin hooks
        self.move_cursor = self.vim_status.cursor.set_cursor_pos
        self.move_cursor_no_end = self.vim_status.cursor.set_cursor_pos_without_end

        cmds = "aAiIvVhHjpPyJkKlLMoOruwWbBegGsSxdcDCnN^$~:%fFtT\"`'m;,.zZ/?=<>{} \b\rq@[]*#"
        cmds = "".join(re.escape(c) for c in cmds)
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.apply_motion_info_in_normal = (
            self.vim_status.cursor.apply_motion_info_in_normal
        )
        self.apply_motion_info_in_yank = (
            self.vim_status.cursor.apply_motion_info_in_yank
        )
        self.executor_colon = ExecutorColon(vim_status)

        self.submodes = ModeSubmodes(vim_status)
        self.viewport_prefix = ViewportPrefixExecutor(vim_status)
        self.file_exit_prefix = FileExitExecutor(vim_status)
        self.operator_motion = OperatorMotionExecutor(vim_status)
        self.change_operator = ChangeOperatorExecutor(vim_status)
        self.delete_operator = DeleteOperatorExecutor(vim_status)
        self.yank_operator = YankOperatorExecutor(vim_status)

    def a(self, count=1, count_text=""):
        """Append text after the cursor."""
        self.vim_status.start_insert("a", count)
        self.vim_status.update_dot_cmd(connect_editor=True)

        cursor = self.get_cursor()
        if not (cursor.atBlockEnd() and cursor.atBlockStart()):
            cursor.movePosition(QTextCursor.Right)
            self.set_cursor(cursor)
        self.vim_status.set_insert_start()
        self.get_editor().setFocus()

    def A(self, count=1, count_text=""):
        """Append text at the end of the line."""
        self.vim_status.start_insert("A", count)
        self.vim_status.update_dot_cmd(connect_editor=True)

        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.EndOfLine)
        self.set_cursor(cursor)
        self.vim_status.set_insert_start()
        self.get_editor().setFocus()

    def i(self, count=1, count_text=""):
        """Insert text before the cursor."""
        self.vim_status.start_insert("i", count)
        self.vim_status.update_dot_cmd(connect_editor=True)
        self.get_editor().setFocus()

    def I(self, count=1, count_text=""):
        """Insert text before the first non-blank in the line."""
        self.vim_status.update_dot_cmd(connect_editor=True)

        motion_info = self.motions.caret(count=count)

        cursor = self.get_cursor()
        cursor.setPosition(motion_info.cursor_pos)
        self.set_cursor(cursor)

        self.get_editor().setFocus()

    def v(self, count=1, count_text=""):
        """Start visual mode per character."""
        self.vim_status.to_visual_char()

    def V(self, count=1, count_text=""):
        """Start visual mode per line."""
        self.vim_status.to_visual_line()

    def J(self, count=1, count_text=""):
        """Join lines, with a minimum of two lines."""
        cursor = self.get_cursor()

        if count > 1:
            count -= 1

        block_no_start = cursor.blockNumber()
        block_no_end = cursor.blockNumber() + count
        cursor_pos_start = cursor.position()

        self.edits.join_lines(cursor_pos_start, block_no_start, block_no_end)

    def o(self, count=1, count_text=""):
        """Begin a new line below the cursor and insert text."""
        self.vim_status.start_insert("o", count)
        editor = self.get_editor()
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.EndOfLine)
        editor.setTextCursor(cursor)
        editor.setFocus()

        # Send the keyevent to editor for using autoindent of editor.
        new_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
        self.vim_status.send_insert_event(editor, new_event)

        self.vim_status.set_insert_start()
        self.vim_status.update_dot_cmd(connect_editor=True)

    def O(self, count=1, count_text=""):
        """Begin a new line above the cursor and insert text."""
        self.vim_status.start_insert("O", count)
        editor = self.get_editor()
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.StartOfLine)
        with self.vim_status.insert_cmd.edit_block():
            cursor.insertText("\n")
        cursor.movePosition(QTextCursor.Up)
        editor.setTextCursor(cursor)
        editor.setFocus()

        self.vim_status.set_insert_start()
        self.vim_status.update_dot_cmd(connect_editor=True)

    def K(self, count=1, count_text=""):
        """Show the help for the keyword under the cursor."""
        self.get_editorstack().inspect_current_object()
        # self.vim_status.set_focus_to_vim_after_delay(500)

    def u(self, count=1, count_text=""):
        """Undo changes."""
        editor = self.get_editor()
        n_block_old = editor.blockCount()

        for _ in range(count):
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
            self.vim_status.set_message(f"{count} changes")

        self.set_cursor_pos(pos)

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_normal, True)])
    def g(self, count=1, count_text=""):
        """Start g submode."""
        return self.submodes.g_prefix

    def G(self, count=1, count_text=""):
        """Move to the line."""
        self.vim_status.push_jump()
        motion_info = self.motions.G(count=count, count_text=count_text)

        self.set_cursor_pos(motion_info.cursor_pos)
        self.vim_status.push_jump()

    def tilde(self, count=1, count_text=""):
        """Switch case of the character under the cursor.

        Move the cursor to the right.
        """
        motion_info = self.motions.l(count, count_text=count_text)

        self.edits.change_case(motion_info, "swap")
        self.set_cursor_pos(motion_info.cursor_pos)

        cursor = self.get_cursor()
        if cursor.atBlockEnd() and not cursor.atBlockStart():
            self.h(1)

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_normal, True)])
    def f(self, count=1, count_text=""):
        """Go to the next occurrence of a character."""
        return self.submodes.find_character

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_normal, True)])
    def F(self, count=1, count_text=""):
        """Go to the next occurrence of a character."""
        return self.submodes.find_character

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_normal, True)])
    def t(self, count=1, count_text=""):
        """Go to the next occurrence of a character."""
        return self.submodes.find_character

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_normal, True)])
    def T(self, count=1, count_text=""):
        """Go to the next occurrence of a character."""
        return self.submodes.find_character

    def r(self, count=1, count_text=""):
        """Replace the ch under the cursor with input."""
        cursor = self.get_cursor()
        pos_start = cursor.position()
        cursor.movePosition(QTextCursor.EndOfBlock)
        pos_block_end = cursor.position()
        if pos_block_end - pos_start < count:
            pos_end = pos_start
        else:
            pos_end = pos_start + count

        executor_sub = self.submodes.replace_character
        executor_sub.pos_start = pos_start
        executor_sub.pos_end = pos_end

        self.set_parent_info_to_submode(executor_sub, count, count_text)

        return ExecutorTransition(executor_sub, True)

    def dot(self, count=1, count_text=""):
        """Run previous change."""
        controller = self.vim_status.put_controller
        if self.vim_status.dot_cmd.put_payload is not None:
            # Keep the literal dot in macros when replaying a snapshot directly.
            controller.repeat(count, count_text)
            return
        controller.cancel()
        # avoid to execute . command twice.
        self.vim_status.manager_macro.remove_last_key(".")
        cmd_str = self.vim_status.dot_cmd.to_cmd_string(count, count_text)

        if not cmd_str:
            return

        cmd_line = self.vim_status.cmd_line
        self.vim_status.running_dot_cmd = True
        try:
            cmd_line.clear()
            for ch in cmd_str:
                cmd_line.setText(cmd_line.text() + ch)

            for key_info in self.vim_status.dot_cmd.key_list_to_cmd_line:
                event = key_info.to_event()
                cmd_line.keyPressEvent(event)

            editor = self.get_editor()
            for key_info in self.vim_status.dot_cmd.key_list_from_editor:
                event = key_info.to_event()
                self.vim_status.send_insert_event(editor, event)

            self.vim_status.finish_insert()
            if count_text and self.vim_status.dot_cmd.cmd in ("i", "a", "A", "o", "O"):
                self.vim_status.dot_cmd.count_text = count_text
        finally:
            self.vim_status.finish_insert(apply_count=False)
            self.vim_status.running_dot_cmd = False

        self.vim_status.set_focus_to_vim()

        cursor_pos = self.get_cursor().position()
        self.vim_status.cursor.set_cursor_pos_without_end(cursor_pos)

    def z(self, count=1, count_text=""):
        """Start z submode."""
        executor_sub = self.viewport_prefix

        self.set_parent_info_to_submode(executor_sub, count, count_text)

        executor_sub.set_func_list_deferred([])

        return ExecutorTransition(executor_sub, True)

    def Z(self, count=1, count_text=""):
        """Start Z submode."""
        executor_sub = self.file_exit_prefix

        self.set_parent_info_to_submode(executor_sub, count, count_text)

        executor_sub.set_func_list_deferred([])

        return ExecutorTransition(executor_sub, True)

    def greater(self, count=1, count_text=""):
        """Shift lines rightwards."""
        executor_sub = self.operator_motion

        self.set_parent_info_to_submode(executor_sub, count, count_text)

        executor_sub.set_func_list_deferred([DeferredAction(self.edits.indent, True)])

        return ExecutorTransition(executor_sub, True)

    def equal(self, count=1, count_text=""):
        """Reindent the lines covered by the following motion."""
        executor_sub = self.operator_motion
        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred([DeferredAction(self.edits.reindent, True)])
        return ExecutorTransition(executor_sub, True)

    def less(self, count=1, count_text=""):
        """Shift lines leftwards."""
        executor_sub = self.operator_motion

        self.set_parent_info_to_submode(executor_sub, count, count_text)

        executor_sub.set_func_list_deferred([DeferredAction(self.edits.unindent, True)])

        return ExecutorTransition(executor_sub, True)

    def quote(self, count=1, count_text=""):
        """Set the name of register."""
        executor_sub = self.submodes.register_prefix

        self.set_parent_info_to_submode(executor_sub, count, count_text)

        executor_sub.set_func_list_deferred([])

        return ExecutorTransition(executor_sub, True)

    def p(self, count=1, count_text=""):
        """Put the text from register after the cursor."""
        self.vim_status.put_controller.put(count, after_cursor=True)

    def P(self, count=1, count_text=""):
        """Put the text from register before the cursor."""
        self.vim_status.put_controller.put(count, after_cursor=False)

    def y(self, count=1, count_text=""):
        """Yank {motion} text into register."""
        executor_sub = self.yank_operator

        self.set_parent_info_to_submode(executor_sub, count, count_text)

        executor_sub.set_func_list_deferred(
            [
                DeferredAction(lambda x: self.edits.yank(x, is_explicit=True), True),
                DeferredAction(self.apply_motion_info_in_yank, True),
            ]
        )

        return ExecutorTransition(executor_sub, True)

    def s(self, count=1, count_text=""):
        """Delete characters and start insert."""
        use_leap = self.vim_status.settings.use_leap
        if use_leap:
            executor_sub = self.submodes.leap_input

            self.set_parent_info_to_submode(executor_sub, count, count_text)

            executor_sub.set_func_list_deferred(
                [DeferredAction(self.apply_motion_info_in_normal, True)]
            )
            return ExecutorTransition(executor_sub, True)
        else:
            motion_info = self.motions.l(count, count_text)
            self.edits.yank(motion_info)
            self.edits.delete(motion_info, is_insert=True)
            self.get_editor().setFocus()

    def S(self, count=1, count_text=""):
        """Delete characters and start insert."""
        use_leap = self.vim_status.settings.use_leap
        if use_leap:
            executor_sub = self.submodes.leap_input

            self.set_parent_info_to_submode(executor_sub, count, count_text)

            executor_sub.set_func_list_deferred(
                [DeferredAction(self.apply_motion_info_in_normal, True)]
            )
            return ExecutorTransition(executor_sub, True)
        else:
            cursor = self.get_cursor()
            block = cursor.block()
            txt = block.text()
            n_space = len(txt) - len(txt.lstrip())

            motion_info = self.motions.j(count - 1, count_text)
            self.edits.yank(motion_info)
            self.edits.delete(motion_info, is_insert=True, replace_txt=" " * n_space)
            self.get_editor().setFocus()

    def x(self, count=1, count_text=""):
        """Delete characters and start insert."""
        cursor_pos = self.get_cursor().position()

        motion_info = self.motions.l(count, count_text)
        self.edits.yank(motion_info)
        self.edits.delete(motion_info, is_insert=False)

        self.vim_status.cursor.set_cursor_pos_without_end(cursor_pos)

    def D(self, count=1, count_text=""):
        """Delete the characters under the cursor until the end of the line.

        If count is greater than 1, This command deletes [count]-1 more lines.
        (not linewise)
        """
        editor = self.get_editor()
        n_block = editor.blockCount()
        block_no_start = self.get_cursor().blockNumber()
        block_no_end = min([n_block - 1, block_no_start + count - 1])
        block = editor.document().findBlockByNumber(block_no_end)

        motion_info = MotionInfo()
        motion_info.cursor_pos = block.position() + block.length() - 1
        motion_info.motion_type = MotionType.CharWise
        sel_start, sel_end = self.edits.yank(motion_info)
        self.edits.delete(motion_info, is_insert=False)

        self.vim_status.cursor.set_cursor_pos_without_end(sel_start)

    def C(self, count=1, count_text=""):
        """Execute D command and start insert mode."""
        editor = self.get_editor()
        n_block = editor.blockCount()
        block_no_start = self.get_cursor().blockNumber()
        block_no_end = min([n_block - 1, block_no_start + count - 1])
        block = editor.document().findBlockByNumber(block_no_end)

        motion_info = MotionInfo()
        motion_info.cursor_pos = block.position() + block.length() - 1
        motion_info.motion_type = MotionType.CharWise
        sel_start, sel_end = self.edits.yank(motion_info)
        self.edits.delete(motion_info, is_insert=True)

        self.vim_status.cursor.set_cursor_pos(sel_start)
        self.get_editor().setFocus()

    def d(self, count=1, count_text=""):
        """Delete text."""
        executor_sub = self.delete_operator

        self.set_parent_info_to_submode(executor_sub, count, count_text)

        executor_sub.set_func_list_deferred(
            [
                DeferredAction(self.edits.yank, True),
                DeferredAction(lambda x: self.edits.delete(x, is_insert=False), True),
            ]
        )

        return ExecutorTransition(executor_sub, True)

    def c(self, count=1, count_text=""):
        """Delete text and start insert."""
        executor_sub = self.change_operator

        self.set_parent_info_to_submode(executor_sub, count, count_text)

        executor_sub.set_func_list_deferred(
            [
                DeferredAction(self.edits.yank, True),
                DeferredAction(lambda x: self.edits.delete(x, is_insert=True), True),
                DeferredAction(self.get_editor().setFocus, False),
            ]
        )

        return ExecutorTransition(executor_sub, True)

    def slash(self, count=1, count_text="", forward=True):
        """Go to the next searched text."""
        self.vim_status.set_message("")
        executor_sub = self.submodes.search_prompt

        self.set_parent_info_to_submode(executor_sub, count, count_text)

        executor_sub.set_func_list_deferred(
            [DeferredAction(self.apply_motion_info_in_normal, True)]
        )
        if not executor_sub.begin(forward):
            return

        return ExecutorTransition(executor_sub, False)

    def question(self, count=1, count_text=""):
        """Search backward from the current position."""
        return self.slash(count, count_text, forward=False)

    def n(self, count=1, count_text=""):
        """Go to the next searched text."""
        self.vim_status.push_jump()
        motion_info = self.motions.n(count=count, count_text=count_text)

        self.set_cursor_pos(motion_info.cursor_pos)
        self.vim_status.push_jump()

    def N(self, count=1, count_text=""):
        """Go to the previous searched text."""
        self.vim_status.push_jump()
        motion_info = self.motions.N(count=count, count_text=count_text)

        self.set_cursor_pos(motion_info.cursor_pos)
        self.vim_status.push_jump()

    def m(self, count=1, count_text=""):
        """Set bookmark with given name."""
        executor_sub = self.submodes.mark_name
        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred(
            [DeferredAction(self.vim_status.bookmark_manager.set_bookmark, True)]
        )
        return ExecutorTransition(executor_sub, True)

    def apostrophe(self, count=1, count_text=""):
        """Jump to bookmark linewise."""
        executor_sub = self.submodes.mark_name
        self.set_parent_info_to_submode(executor_sub, count, count_text)

        def run(ch):
            self.vim_status.push_jump()
            if ch.isupper():
                self.vim_status.bookmark_manager.jump_to_bookmark(ch)
                cursor = self.get_cursor()
                self.vim_status.cursor.set_cursor_pos(cursor.block().position())
            else:
                info = self.motions.apostrophe(ch)
                if info.cursor_pos is not None:
                    self.vim_status.cursor.set_cursor_pos(info.cursor_pos)
            self.vim_status.push_jump()

        executor_sub.set_func_list_deferred([DeferredAction(run, True)])
        return ExecutorTransition(executor_sub, True)

    def backtick(self, count=1, count_text=""):
        """Jump to bookmark charwise."""
        executor_sub = self.submodes.mark_name
        self.set_parent_info_to_submode(executor_sub, count, count_text)

        def run(ch):
            self.vim_status.push_jump()
            if ch.isupper():
                self.vim_status.bookmark_manager.jump_to_bookmark(ch)
            else:
                info = self.motions.backtick(ch)
                if info.cursor_pos is not None:
                    self.vim_status.cursor.set_cursor_pos(info.cursor_pos)
            self.vim_status.push_jump()

        executor_sub.set_func_list_deferred([DeferredAction(run, True)])
        return ExecutorTransition(executor_sub, True)

    def q(self, count=1, count_text=""):
        """Record typed characters into register."""
        if self.vim_status.is_recording_macro():
            self.vim_status.stop_recording_macro()
            self.vim_status.set_message("")
        else:
            executor_sub = self.submodes.mark_name

            self.set_parent_info_to_submode(executor_sub, count, count_text)

            executor_sub.set_func_list_deferred(
                [
                    DeferredAction(self.vim_status.start_recording_macro, True),
                    DeferredAction(lambda: self.vim_status.set_message(""), False),
                ]
            )

            return ExecutorTransition(executor_sub, True)

    def at(self, count=1, count_text=""):
        """Execute contents of register."""
        if self.vim_status.is_recording_macro():
            self.vim_status.manager_macro.remove_last_key("@")
            return

        executor_sub = self.submodes.mark_name

        manager_macro = self.vim_status.manager_macro
        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred(
            [
                DeferredAction(
                    lambda x: manager_macro.set_info_for_execute(x, count), True
                )
            ]
        )

        return ExecutorTransition(executor_sub, True)

    def run_easymotion(self, count=1, count_text=""):
        """Run easymotion."""
        executor_sub = self.submodes.easymotion

        self.set_parent_info_to_submode(executor_sub, count, count_text)

        executor_sub.set_func_list_deferred(
            [DeferredAction(self.apply_motion_info_in_normal, True)]
        )

        return ExecutorTransition(executor_sub, True)

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_normal, True)])
    def opensquarebracket(self, count=1, count_text=""):
        """Start [ submode."""
        return self.submodes.previous_structure

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_normal, True)])
    def closesquarebracket(self, count=1, count_text=""):
        """Start ] submode."""
        return self.submodes.next_structure

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_normal, True)])
    def openbrace(self, count=1, count_text=""):
        """Start { submode."""
        return self.submodes.previous_block

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_normal, True)])
    def closebrace(self, count=1, count_text=""):
        """Start } submode."""
        return self.submodes.next_block

    def asterisk(self, count=1, count_text=""):
        """Search word under cursor forward."""
        motion_info = self.motions.asterisk(count)
        self.apply_motion_info_in_normal(motion_info)

    def sharp(self, count=1, count_text=""):
        """Search word under cursor backward."""
        motion_info = self.motions.sharp(count)
        self.apply_motion_info_in_normal(motion_info)


# Preserve the historically exported class name for external plugin users.
ExecutorNormalCmd = NormalModeExecutor
