# -*- coding: utf-8 -*-
"""Vertical line selection helper."""
# %% Import
# Standard library imports
import re

# Third party imports
from spyder.config.manager import CONF

# Local imports
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
    ExecutorSubCmd_f_t,
    ExecutorSubCmd_g,
    ExecutorSubCmd_r,
    ExecutorSubCmd_register,
    ExecutorSubCmdSneak,
)
from spyder_okvim.spyder.config import CONF_SECTION


class ExecutorVlineCmd(ExecutorBase):
    """Executor for vline."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        cmds = "uUovhydcsSxHjJklLMwWbBepP^$gG~:%fFtTnN/;,\"`'mr<> \b\r*#"
        cmds = "".join(re.escape(c) for c in cmds)
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.set_cursor_pos = vim_status.cursor.set_cursor_pos
        self.set_cursor_pos_in_vline = vim_status.cursor.set_cursor_pos_in_vline
        self.apply_motion_info_in_vline = (
            self.vim_status.cursor.apply_motion_info_in_vline
        )
        self.executor_sub_g = ExecutorSubCmd_g(vim_status)
        self.executor_sub_f_t = ExecutorSubCmd_f_t(vim_status)
        self.executor_sub_r = ExecutorSubCmd_r(vim_status)
        self.executor_sub_register = ExecutorSubCmd_register(vim_status)
        self.executor_sub_alnum = ExecutorSubCmd_alnum(vim_status)
        self.executor_sub_search = ExecutorSearch(vim_status)
        self.executor_sub_easymotion = ExecutorEasymotion(vim_status)
        self.executor_sub_sneak = ExecutorSubCmdSneak(vim_status)
        self.executor_colon = ExecutorColon(vim_status)

    def colon(self, num=1, num_str=""):
        """Start colon mode."""
        self.vim_status.set_message("")
        return RETURN_EXECUTOR_METHOD_INFO(self.executor_colon, False)

    def zero(self, num=1, num_str=""):
        """Go to the start of the current line."""
        motion_info = self.helper_motion.zero()

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def v(self, num=1, num_str=""):
        """Start Visual mode per character."""
        self.vim_status.to_visual_char()

    def h(self, num=1, num_str=""):
        """Move cursor to left."""
        motion_info = self.helper_motion.h(num=num)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def k(self, num=1, num_str=""):
        """Move cursor to up."""
        motion_info = self.helper_motion.k(num=num)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def j(self, num=1, num_str=""):
        """Move cursor to down."""
        motion_info = self.helper_motion.j(num=num)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def H(self, num=1, num_str=""):
        """Move cursor to the top of the page."""
        motion_info = self.helper_motion.H(num=num)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def M(self, num=1, num_str=""):
        """Move cursor to the middle of the page."""
        motion_info = self.helper_motion.M(num=num)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def L(self, num=1, num_str=""):
        """Move cursor to the bottom of the page."""
        motion_info = self.helper_motion.L(num=num)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

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

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def caret(self, num=1, num_str=""):
        """Move cursor to the first non-blank character of the line."""
        motion_info = self.helper_motion.caret(num=num)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def dollar(self, num=1, num_str=""):
        """Move cursor to the end of the line."""
        motion_info = self.helper_motion.dollar(num=num)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def w(self, num=1, num_str=""):
        """Move to the next word."""
        motion_info = self.helper_motion.w(num=num)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def W(self, num=1, num_str=""):
        """Move to the next WORD."""
        motion_info = self.helper_motion.W(num=num)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def b(self, num=1, num_str=""):
        """Move to the previous word."""
        motion_info = self.helper_motion.b(num=num)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def B(self, num=1, num_str=""):
        """Move to the previous WORD."""
        motion_info = self.helper_motion.B(num=num)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def e(self, num=1, num_str=""):
        """Move to the end of the word."""
        motion_info = self.helper_motion.e(num=num)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def g(self, num=1, num_str=""):
        """Start g submode."""
        executor_sub = self.executor_sub_g

        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_vline, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def G(self, num=1, num_str=""):
        """Move to the line."""
        motion_info = self.helper_motion.G(num=num, num_str=num_str)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def tilde(self, num=1, num_str=""):
        """Switch case of the character under the cursor.

        Move the cursor to the start of selection.
        """
        self.helper_action.handle_case(None, "swap")

    def percent(self, num=1, num_str=""):
        """Go to matching bracket."""
        motion_info = self.helper_motion.percent(num=num, num_str=num_str)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def f(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_vline, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def F(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_vline, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def t(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_vline, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def T(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_vline, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def semicolon(self, num=1, num_str=""):
        """Repeat the last ``f``, ``t``, ``F`` or ``T`` search."""
        motion_info = self.helper_motion.semicolon(num=num, num_str=num_str)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def comma(self, num=1, num_str=""):
        """Repeat the last ``f``, ``t``, ``F`` or ``T`` in the opposite direction."""
        motion_info = self.helper_motion.comma(num=num, num_str=num_str)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

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

    def quote(self, num=1, num_str=""):
        """Set the name of register."""
        executor_sub = self.executor_sub_register

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred([])

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def d(self, num=1, num_str=""):
        """Delete text."""
        editor = self.get_editor()
        block_no_start = self.get_block_no_start_in_selection()

        self.helper_action.yank(None)
        self.helper_action.delete(None, is_insert=False)
        self.vim_status.to_normal()

        # calc cursor position
        n_block = editor.blockCount()
        block_no = min([block_no_start, n_block - 1])
        block = editor.document().findBlockByNumber(block_no)
        cursor_pos = block.position()
        txt = block.text()
        cursor_pos += len(txt) - len(txt.lstrip())

        self.set_cursor_pos(cursor_pos)

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
                    FUNC_INFO(self.apply_motion_info_in_vline, True),
                    FUNC_INFO(
                        self.helper_motion.display_another_group_after_sneak, False
                    ),
                ]
            )

            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)
        else:
            self.c(num, num_str)

    def S(self, num=1, num_str=""):
        """Delete text and start insert."""
        use_sneak = CONF.get(CONF_SECTION, "use_sneak")
        if use_sneak:
            executor_sub = self.executor_sub_sneak

            self.set_parent_info_to_submode(executor_sub, num, num_str)

            executor_sub.set_func_list_deferred(
                [
                    FUNC_INFO(self.apply_motion_info_in_vline, True),
                    FUNC_INFO(
                        self.helper_motion.display_another_group_after_rsneak, False
                    ),
                ]
            )

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
            [FUNC_INFO(self.apply_motion_info_in_vline, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, False)

    def n(self, num=1, num_str=""):
        """Go to the next searched text."""
        motion_info = self.helper_motion.n(num=num, num_str=num_str)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def N(self, num=1, num_str=""):
        """Go to the previous searched text."""
        motion_info = self.helper_motion.N(num=num, num_str=num_str)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

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
        self.helper_action.paste_in_vline(num)

    def P(self, num=1, num_str=""):
        """Put the text from register."""
        self.helper_action.paste_in_vline(num)

    def space(self, num=1, num_str=""):
        """Move cursor to right."""
        motion_info = self.helper_motion.space(num=num)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def backspace(self, num=1, num_str=""):
        """Move cursor to left."""
        motion_info = self.helper_motion.backspace(num=num)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def enter(self, num=1, num_str=""):
        """Move cursor to down."""
        motion_info = self.helper_motion.enter(num=num)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def m(self, num=1, num_str=""):
        """Set bookmark with given name."""
        executor_sub = self.executor_sub_alnum
        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.vim_status.set_bookmark, True)]
        )
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def apostrophe(self, num=1, num_str=""):
        """Jump to bookmark linewise keeping vline mode."""
        executor_sub = self.executor_sub_alnum
        self.set_parent_info_to_submode(executor_sub, num, num_str)

        def run(ch):
            if ch.isupper():
                cur = self.vim_status.get_editorstack().get_current_filename()
                self.vim_status.jump_to_bookmark(ch)
                new = self.vim_status.get_editorstack().get_current_filename()
                if cur == new:
                    cursor = self.get_cursor()
                    self.set_cursor_pos_in_vline(cursor.block().position())
                else:
                    cursor = self.get_cursor()
                    self.set_cursor_pos(cursor.block().position())
                    self.vim_status.to_normal()
            else:
                info = self.helper_motion.apostrophe(ch)
                if info.cursor_pos is not None:
                    self.set_cursor_pos_in_vline(info.cursor_pos)

        executor_sub.set_func_list_deferred([FUNC_INFO(run, True)])
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def backtick(self, num=1, num_str=""):
        """Jump to bookmark charwise keeping vline mode."""
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
                    self.set_cursor_pos_in_vline(info.cursor_pos)

        executor_sub.set_func_list_deferred([FUNC_INFO(run, True)])
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def run_easymotion(self, num=1, num_str=""):
        """Run easymotion."""
        executor_sub = self.executor_sub_easymotion

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_vline, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def asterisk(self, num=1, num_str=""):
        """Search word under cursor forward."""
        motion_info = self.helper_motion.asterisk(num)
        self.apply_motion_info_in_vline(motion_info)

    def sharp(self, num=1, num_str=""):
        """Search word under cursor backward."""
        motion_info = self.helper_motion.sharp(num)
        self.apply_motion_info_in_vline(motion_info)
