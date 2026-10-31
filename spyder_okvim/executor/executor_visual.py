# -*- coding: utf-8 -*-
"""Executor for visual mode commands.

The :class:`VisualModeExecutor` interprets keystrokes while a text selection is
active.  Many commands mirror those from :mod:`executor_normal`, but they act on
the current selection.  The executor can also enter submodes to handle searches,
character motions and other modal operations.
"""

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
from spyder_okvim.executor.executor_surround import ExecutorAddSurround
from spyder_okvim.executor.mixins import MovementMixin, SelectionMixin
from spyder_okvim.executor.prefixes import ModeSubmodes


class VisualModeExecutor(SelectionMixin, MovementMixin, ExecutorBase):
    """Interpret keys for a characterwise Visual selection."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        # MovementMixin hooks
        self.move_cursor = vim_status.cursor.set_cursor_pos_in_visual
        self.move_cursor_no_end = vim_status.cursor.set_cursor_pos_in_visual

        cmds = "uUoiaydxscVhHjJklLMwWbBSepP^$gG~:%fFtTnN/?;,\"`'mr<>{} \b\r[]*#"
        cmds = "".join(re.escape(c) for c in cmds)
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.set_cursor_pos = vim_status.cursor.set_cursor_pos
        self.set_cursor_pos_in_visual = vim_status.cursor.set_cursor_pos_in_visual
        self.apply_motion_info_in_visual = (
            self.vim_status.cursor.apply_motion_info_in_visual
        )
        self.executor_colon = ExecutorColon(vim_status)
        self.submodes = ModeSubmodes(vim_status)
        self.add_surround = ExecutorAddSurround(vim_status)

        # SelectionMixin hooks
        self.apply_motion_info_in_sel = self.apply_motion_info_in_visual
        self.set_cursor_pos_in_sel = self.set_cursor_pos_in_visual

    def V(self, count=1, count_text=""):
        """Start Visual mode per line."""
        self.vim_status.to_visual_line()

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

    def l(self, count=1, count_text=""):
        """Move cursor to right."""
        motion_info = self.motions.l(count=count)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_visual, True)])
    def g(self, count=1, count_text=""):
        """Start g submode."""
        return self.submodes.g_prefix

    def G(self, count=1, count_text=""):
        """Move to the line."""
        motion_info = self.motions.G(count=count, count_text=count_text)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def tilde(self, count=1, count_text=""):
        """Switch case of the character under the cursor.

        Move the cursor to the start of selection.
        """
        self.edits.change_case(None, "swap")

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_visual, True)])
    def f(self, count=1, count_text=""):
        """Go to the next occurrence of a character."""
        return self.submodes.find_character

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_visual, True)])
    def F(self, count=1, count_text=""):
        """Go to the next occurrence of a character."""
        return self.submodes.find_character

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_visual, True)])
    def t(self, count=1, count_text=""):
        """Go to the next occurrence of a character."""
        return self.submodes.find_character

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_visual, True)])
    def T(self, count=1, count_text=""):
        """Go to the next occurrence of a character."""
        return self.submodes.find_character

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_visual, True)])
    def opensquarebracket(self, count=1, count_text=""):
        """Start [ submode."""
        return self.submodes.previous_structure

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_visual, True)])
    def closesquarebracket(self, count=1, count_text=""):
        """Start ] submode."""
        return self.submodes.next_structure

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_visual, True)])
    def openbrace(self, count=1, count_text=""):
        """Start { submode."""
        return self.submodes.previous_block

    @submode(lambda self: [DeferredAction(self.apply_motion_info_in_visual, True)])
    def closebrace(self, count=1, count_text=""):
        """Start } submode."""
        return self.submodes.next_block

    def d(self, count=1, count_text=""):
        """Delete text."""
        sel_start, sel_end = self.edits.yank(None)
        self.edits.delete(None, is_insert=False)
        self.vim_status.to_normal()
        self.set_cursor_pos(sel_start)
        cursor = self.get_cursor()
        if cursor.atBlockEnd() and not cursor.atBlockStart():
            self.set_cursor_pos(sel_start - 1)

    def S(self, count=1, count_text=""):
        """Add surroundings: parentheses, brackets, quotes."""
        self.vim_status.set_message("")
        executor_sub = self.add_surround

        executor_sub.pos_start = self.get_pos_start_in_selection()
        executor_sub.pos_end = self.get_pos_end_in_selection()

        return ExecutorTransition(executor_sub, True)


# Preserve the historically exported class name for external plugin users.
ExecutorVisualCmd = VisualModeExecutor
