# -*- coding: utf-8 -*-
"""Interpret Visual-line input while preserving whole-line selection semantics."""

# Standard Libraries
import re

# Project Libraries
from spyder_okvim.executor.decorators import submode
from spyder_okvim.executor.executor_base import (
    DeferredAction,
    ExecutorBase,
    ExecutorTransition,
)
from spyder_okvim.executor.executor_colon import ExecutorColon
from spyder_okvim.executor.mixins import MovementMixin, SelectionMixin
from spyder_okvim.executor.prefixes import ModeSubmodes


class VisualLineModeExecutor(SelectionMixin, MovementMixin, ExecutorBase):
    """Interpret keys for a linewise Visual selection and preserve its endpoints."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        # MovementMixin hooks
        self.move_cursor = vim_status.cursor.set_cursor_pos_in_vline
        self.move_cursor_no_end = vim_status.cursor.set_cursor_pos_in_vline

        cmds = "uUovhiyadcsSxHjJklLMwWbBepP^$gG~:%fFtTnN/?;,\"`'mr<>{} \b\r[]*#"
        cmds = "".join(re.escape(c) for c in cmds)
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.set_cursor_pos = vim_status.cursor.set_cursor_pos
        self.set_cursor_pos_in_vline = vim_status.cursor.set_cursor_pos_in_vline
        self.apply_motion_info_in_vline = (
            self.vim_status.cursor.apply_motion_info_in_vline
        )
        self.submodes = ModeSubmodes(vim_status)
        self.executor_colon = ExecutorColon(vim_status)

        # SelectionMixin hooks
        self.apply_motion_info_in_sel = self.apply_motion_info_in_vline
        self.set_cursor_pos_in_sel = self.set_cursor_pos_in_vline

    def v(self, count=1, count_text=""):
        """Start Visual mode per character."""
        self.vim_status.to_visual_char()

    def J(self, count=1, count_text=""):
        """Join lines, with a minimum of two lines."""
        block_no_start = self.get_block_no_start_in_selection()
        block_no_end = self.get_block_no_end_in_selection()

        if block_no_start is None:
            self.vim_status.to_normal()
            return

        if block_no_start == block_no_end:
            block_no_end += 1

        cursor_pos_start = self.get_pos_start_in_selection()
        self.edits.join_lines(cursor_pos_start, block_no_start, block_no_end)
        self.vim_status.to_normal()

    def g(self, count=1, count_text=""):
        """Start g submode."""
        executor_sub = self.submodes.g_prefix

        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred(
            [DeferredAction(self.apply_motion_info_in_vline, True)]
        )

        return ExecutorTransition(executor_sub, True)

    def G(self, count=1, count_text=""):
        """Move to the line."""
        motion_info = self.motions.G(count=count, count_text=count_text)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def tilde(self, count=1, count_text=""):
        """Switch case of the character under the cursor.

        Move the cursor to the start of selection.
        """
        self.edits.change_case(None, "swap")

    def f(self, count=1, count_text=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.submodes.find_character

        self.set_parent_info_to_submode(executor_sub, count, count_text)

        executor_sub.set_func_list_deferred(
            [DeferredAction(self.apply_motion_info_in_vline, True)]
        )

        return ExecutorTransition(executor_sub, True)

    def F(self, count=1, count_text=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.submodes.find_character

        self.set_parent_info_to_submode(executor_sub, count, count_text)

        executor_sub.set_func_list_deferred(
            [DeferredAction(self.apply_motion_info_in_vline, True)]
        )

        return ExecutorTransition(executor_sub, True)

    def t(self, count=1, count_text=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.submodes.find_character

        self.set_parent_info_to_submode(executor_sub, count, count_text)

        executor_sub.set_func_list_deferred(
            [DeferredAction(self.apply_motion_info_in_vline, True)]
        )

        return ExecutorTransition(executor_sub, True)

    def T(self, count=1, count_text=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.submodes.find_character

        self.set_parent_info_to_submode(executor_sub, count, count_text)

        executor_sub.set_func_list_deferred(
            [DeferredAction(self.apply_motion_info_in_vline, True)]
        )

        return ExecutorTransition(executor_sub, True)

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_vline, True)])
    def opensquarebracket(self, count=1, count_text=""):
        """Start [ submode."""
        return self.submodes.previous_structure

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_vline, True)])
    def closesquarebracket(self, count=1, count_text=""):
        """Start ] submode."""
        return self.submodes.next_structure

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_vline, True)])
    def openbrace(self, count=1, count_text=""):
        """Start { submode."""
        return self.submodes.previous_block

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_vline, True)])
    def closebrace(self, count=1, count_text=""):
        """Start } submode."""
        return self.submodes.next_block

    def d(self, count=1, count_text=""):
        """Delete text."""
        editor = self.get_editor()
        block_no_start = self.get_block_no_start_in_selection()

        self.edits.yank(None)
        self.edits.delete(None, is_insert=False)
        self.vim_status.to_normal()

        # calc cursor position
        n_block = editor.blockCount()
        block_no = min([block_no_start, n_block - 1])
        block = editor.document().findBlockByNumber(block_no)
        cursor_pos = block.position()
        txt = block.text()
        cursor_pos += len(txt) - len(txt.lstrip())

        self.set_cursor_pos(cursor_pos)

    def S(self, count=1, count_text=""):
        """Delete text and start insert."""
        use_leap = self.vim_status.settings.use_leap
        if use_leap:
            executor_sub = self.submodes.leap_input

            self.set_parent_info_to_submode(executor_sub, count, count_text)

            executor_sub.set_func_list_deferred(
                [DeferredAction(self.apply_motion_info_in_vline, True)]
            )

            return ExecutorTransition(executor_sub, True)


# Preserve the historically exported class name for external plugin users.
ExecutorVlineCmd = VisualLineModeExecutor
