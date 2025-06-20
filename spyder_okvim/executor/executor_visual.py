# -*- coding: utf-8 -*-
"""Executor for visual mode commands.

The :class:`ExecutorVisualCmd` interprets keystrokes while a text selection is
active.  Many commands mirror those from :mod:`executor_normal`, but they act on
the current selection.  The executor can also enter submodes to handle searches,
character motions and other modal operations.
"""
# %% Import
# Standard library imports
import re

# Third party imports
from spyder.config.manager import CONF

from spyder_okvim.executor.decorators import submode

# Local imports
from spyder_okvim.executor.executor_base import (
    FUNC_INFO,
    RETURN_EXECUTOR_METHOD_INFO,
    ExecutorBase,
)
from spyder_okvim.executor.mixins import MovementMixin
from spyder_okvim.executor.executor_colon import ExecutorColon
from spyder_okvim.executor.executor_easymotion import ExecutorEasymotion
from spyder_okvim.executor.executor_sub import (
    ExecutorSearch,
    ExecutorSubCmd_alnum,
    ExecutorSubCmd_f_t,
    ExecutorSubCmd_g,
    ExecutorSubCmd_r,
    ExecutorSubCmd_register,
    ExecutorSubCmdSneak,
    ExecutorSubMotion_a,
    ExecutorSubMotion_i,
)
from spyder_okvim.executor.executor_surround import ExecutorAddSurround
from spyder_okvim.spyder.config import CONF_SECTION


class ExecutorVisualCmd(MovementMixin, ExecutorBase):
    """Executor for visual mode."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        # MovementMixin hooks
        self.move_cursor = vim_status.cursor.set_cursor_pos_in_visual
        self.move_cursor_no_end = vim_status.cursor.set_cursor_pos_in_visual

        cmds = "uUoiaydxscVhHjJklLMwWbBSepP^$gG~:%fFtTnN/;,\"`'mr<> \b\r*#"
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



    def r(self, num=1, num_str=""):
        """Replace the selected text under the cursor with input."""
        executor_sub = self.executor_sub_r
        executor_sub.pos_start = self.get_pos_start_in_selection()
        executor_sub.pos_end = self.get_pos_end_in_selection()

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [
                FUNC_INFO(self.vim_status.to_normal, False),
                FUNC_INFO(lambda: self.set_cursor_pos(executor_sub.pos_start), False),
            ]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def greater(self, num=1, num_str=""):
        """Shift lines rightwards."""
        sel_start = self.get_pos_start_in_selection()
        sel_end = self.get_pos_end_in_selection()
        self.helper_action._indent(sel_start, sel_end)
        self.vim_status.to_normal()
        self.vim_status.cursor.draw_vim_cursor()

    def less(self, num=1, num_str=""):
        """Shift lines leftwards."""
        sel_start = self.get_pos_start_in_selection()
        sel_end = self.get_pos_end_in_selection()
        self.helper_action._unindent(sel_start, sel_end)
        self.vim_status.to_normal()
        self.vim_status.cursor.draw_vim_cursor()

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

    def quote(self, num=1, num_str=""):
        """Set the name of register."""
        executor_sub = self.executor_sub_register

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred([])

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

    def x(self, num=1, num_str=""):
        """Delete text."""
        self.d(num, num_str)

    def c(self, num=1, num_str=""):
        """Delete text and start insert."""
        sel_start, sel_end = self.helper_action.yank(None)
        self.helper_action.delete(None, is_insert=True)
        self.vim_status.to_normal()
        self.set_cursor_pos(sel_start)
        self.get_editor().setFocus()

    def s(self, num=1, num_str=""):
        """Delete text and start insert."""
        use_sneak = CONF.get(CONF_SECTION, "use_sneak")
        if use_sneak:
            executor_sub = self.executor_sub_sneak

            self.set_parent_info_to_submode(executor_sub, num, num_str)

            executor_sub.set_func_list_deferred(
                [
                    FUNC_INFO(self.apply_motion_info_in_visual, True),
                    FUNC_INFO(
                        self.helper_motion.display_another_group_after_sneak, False
                    ),
                ]
            )

            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)
        else:
            self.c(num, num_str)

    def S(self, num=1, num_str=""):
        """Add surroundings: parentheses, brackets, quotes."""
        self.vim_status.set_message("")
        executor_sub = self.executor_sub_surround

        executor_sub.pos_start = self.get_pos_start_in_selection()
        executor_sub.pos_end = self.get_pos_end_in_selection()

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def y(self, num=1, num_str=""):
        """Yank selected text."""
        sel_start, sel_end = self.helper_action.yank(None, is_explicit=True)

        self.vim_status.to_normal()
        self.set_cursor_pos(sel_start)

    def slash(self, num=1, num_str=""):
        """Go to the next searched text."""
        self.vim_status.set_message("")
        executor_sub = self.executor_sub_search

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_visual, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, False)

    def n(self, num=1, num_str=""):
        """Go to the next searched text."""
        motion_info = self.helper_motion.n(num=num, num_str=num_str)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def N(self, num=1, num_str=""):
        """Go to the previous searched text."""
        motion_info = self.helper_motion.N(num=num, num_str=num_str)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def o(self, num=1, num_str=""):
        """Go to other end of highlighted text."""
        sel_start = self.vim_status.get_pos_start_in_selection()
        sel_end = self.vim_status.get_pos_end_in_selection()
        cur_pos = self.get_cursor().position()
        if abs(sel_start - cur_pos) < abs(sel_end - cur_pos):
            new_pos = sel_end - 1
        else:
            new_pos = sel_start
        self.set_cursor_pos(new_pos)

    def u(self, num=1, num_str=""):
        """Make txt lowercase and move cursor to the start of selection."""
        self.helper_action.handle_case(None, "lower")

    def U(self, num=1, num_str=""):
        """Make txt uppercase and move cursor to the start of selection."""
        self.helper_action.handle_case(None, "upper")

    def p(self, num=1, num_str=""):
        """Put the text from register."""
        self.helper_action.paste_in_visual(num)

    def P(self, num=1, num_str=""):
        """Put the text from register."""
        self.helper_action.paste_in_visual(num)



    def m(self, num=1, num_str=""):
        """Set bookmark with given name."""
        executor_sub = self.executor_sub_alnum
        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.vim_status.set_bookmark, True)]
        )
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def apostrophe(self, num=1, num_str=""):
        """Jump to bookmark linewise keeping visual mode."""
        executor_sub = self.executor_sub_alnum
        self.set_parent_info_to_submode(executor_sub, num, num_str)

        def run(ch):
            if ch.isupper():
                cur = self.vim_status.get_editorstack().get_current_filename()
                self.vim_status.jump_to_bookmark(ch)
                new = self.vim_status.get_editorstack().get_current_filename()
                if cur == new:
                    cursor = self.get_cursor()
                    self.set_cursor_pos_in_visual(cursor.block().position())
                else:
                    cursor = self.get_cursor()
                    self.set_cursor_pos(cursor.block().position())
                    self.vim_status.to_normal()
            else:
                info = self.helper_motion.apostrophe(ch)
                if info.cursor_pos is not None:
                    self.set_cursor_pos_in_visual(info.cursor_pos)

        executor_sub.set_func_list_deferred([FUNC_INFO(run, True)])
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def backtick(self, num=1, num_str=""):
        """Jump to bookmark charwise keeping visual mode."""
        executor_sub = self.executor_sub_alnum
        self.set_parent_info_to_submode(executor_sub, num, num_str)

        def run(ch):
            if ch.isupper():
                cur = self.vim_status.get_editorstack().get_current_filename()
                self.vim_status.jump_to_bookmark(ch)
                new = self.vim_status.get_editorstack().get_current_filename()
                if cur != new:
                    self.vim_status.to_normal()
            else:
                info = self.helper_motion.backtick(ch)
                if info.cursor_pos is not None:
                    self.set_cursor_pos_in_visual(info.cursor_pos)

        executor_sub.set_func_list_deferred([FUNC_INFO(run, True)])
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def run_easymotion(self, num=1, num_str=""):
        """Run easymotion."""
        executor_sub = self.executor_sub_easymotion

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_visual, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def asterisk(self, num=1, num_str=""):
        """Search word under cursor forward."""
        motion_info = self.helper_motion.asterisk(num)
        self.apply_motion_info_in_visual(motion_info)

    def sharp(self, num=1, num_str=""):
        """Search word under cursor backward."""
        motion_info = self.helper_motion.sharp(num)
        self.apply_motion_info_in_visual(motion_info)
