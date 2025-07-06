# -*- coding: utf-8 -*-
"""Executor for visual mode commands.

The :class:`ExecutorVisualCmd` interprets keystrokes while a text selection is
active.  Many commands mirror those from :mod:`executor_normal`, but they act on
the current selection.  The executor can also enter submodes to handle searches,
character motions and other modal operations.
"""

# Standard Libraries
import re

# Third Party Libraries
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
    ExecutorSubCmdSneak,
    ExecutorSubMotion_a,
    ExecutorSubMotion_i,
)
from spyder_okvim.executor.executor_surround import ExecutorAddSurround
from spyder_okvim.executor.mixins import MovementMixin, SelectionMixin
from spyder_okvim.spyder.config import CONF_SECTION


class ExecutorVisualCmd(SelectionMixin, MovementMixin, ExecutorBase):
    """Executor for visual mode."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        # MovementMixin hooks
        self.move_cursor = vim_status.cursor.set_cursor_pos_in_visual
        self.move_cursor_no_end = vim_status.cursor.set_cursor_pos_in_visual

        cmds = "uUoiaydxscVhHjJklLMwWbBSepP^$gG~:%fFtTnN/;,\"`'mr<>{} \b\r[]*#"
        cmds = "".join(re.escape(c) for c in cmds)
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.set_cursor_pos = vim_status.cursor.set_cursor_pos
        self.set_cursor_pos_in_visual = vim_status.cursor.set_cursor_pos_in_visual
        self.apply_motion_info_in_visual = (
            self.vim_status.cursor.apply_motion_info_in_visual
        )
        self.set_block_selection_in_visual = (
            self.vim_status.cursor.set_block_selection_in_visual
        )
        self.executor_colon = ExecutorColon(vim_status)
        self.executor_sub_g = ExecutorSubCmd_g(vim_status)
        self.executor_sub_f_t = ExecutorSubCmd_f_t(vim_status)
        self.executor_sub_r = ExecutorSubCmd_r(vim_status)
        self.executor_sub_motion_i = ExecutorSubMotion_i(vim_status)
        self.executor_sub_motion_a = ExecutorSubMotion_a(vim_status)
        self.executor_sub_register = ExecutorSubCmd_register(vim_status)
        self.executor_sub_alnum = ExecutorSubCmd_alnum(vim_status)
        self.executor_sub_search = ExecutorSearch(vim_status)
        self.executor_sub_easymotion = ExecutorEasymotion(vim_status)
        self.executor_sub_sneak = ExecutorSubCmdSneak(vim_status)
        self.executor_sub_surround = ExecutorAddSurround(vim_status)
        self.executor_sub_opensquarebracekt = ExecutorSubCmd_opensquarebracket(
            vim_status
        )
        self.executor_sub_closesquarebracekt = (
            ExecutorSubCmd_closesquarebracket(vim_status)
        )
        self.executor_sub_openbrace = ExecutorSubCmd_openbrace(vim_status)
        self.executor_sub_closebrace = ExecutorSubCmd_closebrace(vim_status)

        # SelectionMixin hooks
        self.apply_motion_info_in_sel = self.apply_motion_info_in_visual
        self.set_cursor_pos_in_sel = self.set_cursor_pos_in_visual
        self.paste_in_sel = self.helper_action.paste_in_visual

    def V(self, num=1, num_str=""):
        """Start Visual mode per line."""
        self.vim_status.to_visual_line()

    def J(self, num=1, num_str=""):
        """Join lines, with a minimum of two lines."""
        block_no_start = self.get_block_no_start_in_selection()
        block_no_end = self.get_block_no_end_in_selection()

        if block_no_start is None:
            self.vim_status.to_normal()
            return

        if block_no_start == block_no_end:
            block_no_end += 1

        cursor_pos_start = self.get_pos_start_in_selection()
        self.helper_action.join_lines(cursor_pos_start, block_no_start, block_no_end)
        self.vim_status.to_normal()

    def l(self, num=1, num_str=""):
        """Move cursor to right."""
        motion_info = self.helper_motion.l(num=num)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_visual, True)])
    def g(self, num=1, num_str=""):
        """Start g submode."""
        return self.executor_sub_g

    def G(self, num=1, num_str=""):
        """Move to the line."""
        motion_info = self.helper_motion.G(num=num, num_str=num_str)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def tilde(self, num=1, num_str=""):
        """Switch case of the character under the cursor.

        Move the cursor to the start of selection.
        """
        self.helper_action.handle_case(None, "swap")

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_visual, True)])
    def f(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        return self.executor_sub_f_t

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_visual, True)])
    def F(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        return self.executor_sub_f_t

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_visual, True)])
    def t(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        return self.executor_sub_f_t

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_visual, True)])
    def T(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        return self.executor_sub_f_t

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_visual, True)])
    def opensquarebracket(self, num=1, num_str=""):
        """Start [ submode."""
        return self.executor_sub_opensquarebracekt

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_visual, True)])
    def closesquarebracket(self, num=1, num_str=""):
        """Start ] submode."""
        return self.executor_sub_closesquarebracekt

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_visual, True)])
    def openbrace(self, num=1, num_str=""):
        """Start { submode."""
        return self.executor_sub_openbrace

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_visual, True)])
    def closebrace(self, num=1, num_str=""):
        """Start } submode."""
        return self.executor_sub_closebrace

    def i(self, num=1, num_str=""):
        """Select block exclusively."""
        executor_sub = self.executor_sub_motion_i

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.set_block_selection_in_visual, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def a(self, num=1, num_str=""):
        """Select block exclusively."""
        executor_sub = self.executor_sub_motion_a

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.set_block_selection_in_visual, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def d(self, num=1, num_str=""):
        """Delete text."""
        sel_start, sel_end = self.helper_action.yank(None)
        self.helper_action.delete(None, is_insert=False)
        self.vim_status.to_normal()
        self.set_cursor_pos(sel_start)
        cursor = self.get_cursor()
        if cursor.atBlockEnd() and not cursor.atBlockStart():
            self.set_cursor_pos(sel_start - 1)

    def S(self, num=1, num_str=""):
        """Add surroundings: parentheses, brackets, quotes."""
        self.vim_status.set_message("")
        executor_sub = self.executor_sub_surround

        executor_sub.pos_start = self.get_pos_start_in_selection()
        executor_sub.pos_end = self.get_pos_end_in_selection()

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)
