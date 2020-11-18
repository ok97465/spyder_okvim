# -*- coding: utf-8 -*-
"""."""
# %% Import
# Standard library imports
import re

# Local imports
from spyder_okvim.executor.executor_base import (
    FUNC_INFO, RETURN_EXECUTOR_METHOD_INFO, ExecutorBase,)
from spyder_okvim.executor.executor_sub import (
    ExecutorSearch, ExecutorSubCmd_f_t, ExecutorSubCmd_g, ExecutorSubCmd_r,
    ExecutorSubCmd_register, ExecutorSubMotion_a, ExecutorSubMotion_i,)


class ExecutorVisualCmd(ExecutorBase):
    """Executor for visual mode."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        cmds = 'uUoiaydxscVhHjJklLMwWbepP^$gG~%fFtTnN/;,"r<> \b'
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.set_cursor_pos = vim_status.cursor.set_cursor_pos
        self.set_cursor_pos_in_visual = \
            vim_status.cursor.set_cursor_pos_in_visual
        self.apply_motion_info_in_visual = \
            self.vim_status.cursor.apply_motion_info_in_visual
        self.set_block_selection_in_visual = \
            self.vim_status.cursor.set_block_selection_in_visual
        self.executor_sub_g = ExecutorSubCmd_g(vim_status)
        self.executor_sub_f_t = ExecutorSubCmd_f_t(vim_status)
        self.executor_sub_r = ExecutorSubCmd_r(vim_status)
        self.executor_sub_motion_i = ExecutorSubMotion_i(vim_status)
        self.executor_sub_motion_a = ExecutorSubMotion_a(vim_status)
        self.executor_sub_register = ExecutorSubCmd_register(vim_status)
        self.executor_sub_search = ExecutorSearch(vim_status)

    def zero(self, num=1, num_str=''):
        """Go to the start of the current line."""
        motion_info = self.helper_motion.zero()

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def V(self, num=1, num_str=''):
        """Start Visual mode per line."""
        self.vim_status.to_visual_line()

    def h(self, num=1, num_str=''):
        """Move cursor to left."""
        motion_info = self.helper_motion.h(num=num)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def k(self, num=1, num_str=''):
        """Move cursor to up."""
        motion_info = self.helper_motion.k(num=num)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def H(self, num=1, num_str=''):
        """Move cursor to the top of the page."""
        motion_info = self.helper_motion.H(num=num)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def M(self, num=1, num_str=''):
        """Move cursor to the middle of the page."""
        motion_info = self.helper_motion.M(num=num)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def L(self, num=1, num_str=''):
        """Move cursor to the bottom of the page."""
        motion_info = self.helper_motion.L(num=num)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def j(self, num=1, num_str=''):
        """Move cursor to down."""
        motion_info = self.helper_motion.j(num=num)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def J(self, num=1, num_str=''):
        """Join lines, with a minimum of two lines."""
        block_no_start = self.get_block_no_start_in_selection()
        block_no_end = self.get_block_no_end_in_selection()

        if block_no_start is None:
            self.vim_status.to_normal()
            return

        if block_no_start == block_no_end:
            block_no_end += 1

        cursor_pos_start = self.get_pos_start_in_selection()
        self.helper_action.join_lines(cursor_pos_start,
                                      block_no_start, block_no_end)
        self.vim_status.to_normal()

    def l(self, num=1, num_str=''):
        """Move cursor to right."""
        motion_info = self.helper_motion.l(num=num)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def caret(self, num=1, num_str=''):
        """Move cursor to the first non-blank character of the line."""
        motion_info = self.helper_motion.caret(num=num)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def dollar(self, num=1, num_str=''):
        """Move cursor to the end of the line."""
        motion_info = self.helper_motion.dollar(num=num)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def w(self, num=1, num_str=''):
        """Move to the next word."""
        motion_info = self.helper_motion.w(num=num)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def W(self, num=1, num_str=''):
        """Move to the next WORD."""
        motion_info = self.helper_motion.W(num=num)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def b(self, num=1, num_str=''):
        """Move to the previous word."""
        motion_info = self.helper_motion.b(num=num)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def e(self, num=1, num_str=''):
        """Move to the the end of word."""
        motion_info = self.helper_motion.e(num=num)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def g(self, num=1, num_str=''):
        """Start g submode."""
        executor_sub = self.executor_sub_g

        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_visual, True)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def G(self, num=1, num_str=''):
        """Move to the line."""
        motion_info = self.helper_motion.G(num=num,
                                           num_str=num_str)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def tilde(self, num=1, num_str=''):
        """Switch case of the character under the cursor.

        Move the cursor to the start of selection.
        """
        self.helper_action.handle_case(None, 'swap')

    def percent(self, num=1, num_str=''):
        """Go to matching bracket."""
        motion_info = self.helper_motion.percent(num=num,
                                                 num_str=num_str)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def f(self, num=1, num_str=''):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_visual, True)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def F(self, num=1, num_str=''):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_visual, True)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def t(self, num=1, num_str=''):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_visual, True)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def T(self, num=1, num_str=''):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_visual, True)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def semicolon(self, num=1, num_str=''):
        """Repeat latest f, t, f, T."""
        motion_info = self.helper_motion.semicolon(num=num,
                                                   num_str=num_str)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def comma(self, num=1, num_str=''):
        """Repeat latest f, t, f, T in opposite direction."""
        motion_info = self.helper_motion.comma(num=num,
                                               num_str=num_str)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def r(self, num=1, num_str=''):
        """Replace the selected text under the cursor with input."""
        executor_sub = self.executor_sub_r
        executor_sub.pos_start = self.get_pos_start_in_selection()
        executor_sub.pos_end = self.get_pos_end_in_selection()

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.vim_status.to_normal, False),
             FUNC_INFO(
                 lambda: self.set_cursor_pos(executor_sub.pos_start),
                 False)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def greater(self, num=1, num_str=''):
        """Shift lines rightwards."""
        sel_start = self.get_pos_start_in_selection()
        sel_end = self.get_pos_end_in_selection()
        self.helper_action._indent(sel_start, sel_end)
        self.vim_status.to_normal()
        self.vim_status.cursor.draw_vim_cursor()

    def less(self, num=1, num_str=''):
        """Shift lines leftwards."""
        sel_start = self.get_pos_start_in_selection()
        sel_end = self.get_pos_end_in_selection()
        self.helper_action._unindent(sel_start, sel_end)
        self.vim_status.to_normal()
        self.vim_status.cursor.draw_vim_cursor()

    def i(self, num=1, num_str=''):
        """Select block exclusively."""
        executor_sub = self.executor_sub_motion_i

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.set_block_selection_in_visual, True)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def a(self, num=1, num_str=''):
        """Select block exclusively."""
        executor_sub = self.executor_sub_motion_a

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.set_block_selection_in_visual, True)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def quote(self, num=1, num_str=''):
        """Set the name of register."""
        executor_sub = self.executor_sub_register

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred([])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def d(self, num=1, num_str=''):
        """Delete text."""
        sel_start, sel_end = self.helper_action.yank(None)
        self.helper_action.delete(None, is_insert=False)
        self.vim_status.to_normal()
        self.set_cursor_pos(sel_start)
        cursor = self.get_cursor()
        if cursor.atBlockEnd() and not cursor.atBlockStart():
            self.set_cursor_pos(sel_start - 1)

    def x(self, num=1, num_str=''):
        """Delete text."""
        self.d(num, num_str)

    def c(self, num=1, num_str=''):
        """Delete text and start insert."""
        sel_start, sel_end = self.helper_action.yank(None)
        self.helper_action.delete(None, is_insert=True)
        self.vim_status.to_normal()
        self.set_cursor_pos(sel_start)
        self.get_editor().setFocus()

    def s(self, num=1, num_str=''):
        """Delete text and start insert."""
        self.c(num, num_str)

    def y(self, num=1, num_str=''):
        """Yank selected text."""
        sel_start, sel_end = self.helper_action.yank(None, is_explicit=True)

        self.vim_status.to_normal()
        self.set_cursor_pos(sel_start)

    def slash(self, num=1, num_str=''):
        """Go to the next searched text."""
        executor_sub = self.executor_sub_search

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred([
            FUNC_INFO(self.apply_motion_info_in_visual, True)])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, False)

    def n(self, num=1, num_str=''):
        """Go to the next searched text."""
        motion_info = self.helper_motion.n(num=num, num_str=num_str)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def N(self, num=1, num_str=''):
        """Go to the previous searched text."""
        motion_info = self.helper_motion.N(num=num, num_str=num_str)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def o(self, num=1, num_str=''):
        """Go to other end of highlighted text."""
        sel_start = self.vim_status.get_pos_start_in_selection()
        sel_end = self.vim_status.get_pos_end_in_selection()
        cur_pos = self.get_cursor().position()
        if abs(sel_start - cur_pos) < abs(sel_end - cur_pos):
            new_pos = sel_end - 1
        else:
            new_pos = sel_start
        self.set_cursor_pos(new_pos)

    def u(self, num=1, num_str=''):
        """Make txt lowercase and move cursor to the start of selection."""
        self.helper_action.handle_case(None, 'lower')

    def U(self, num=1, num_str=''):
        """Make txt uppercase and move cursor to the start of selection."""
        self.helper_action.handle_case(None, 'upper')

    def p(self, num=1, num_str=''):
        """Put the text from register."""
        self.helper_action.paste_in_visual(num)

    def P(self, num=1, num_str=''):
        """Put the text from register."""
        self.helper_action.paste_in_visual(num)

    def space(self, num=1, num_str=''):
        """Move cursor to right."""
        motion_info = self.helper_motion.space(num=num)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def backspace(self, num=1, num_str=''):
        """Move cursor to left."""
        motion_info = self.helper_motion.backspace(num=num)

        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

