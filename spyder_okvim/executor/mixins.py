# -*- coding: utf-8 -*-
"""Mixin classes used by command executors."""

# Standard Libraries
from typing import Callable

# Third Party Libraries
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.executor.executor_base import FUNC_INFO, RETURN_EXECUTOR_METHOD_INFO
from spyder_okvim.spyder.config import CONF_SECTION


class MovementMixin:
    """Provide cursor movement commands for various executor classes.

    Subclasses must define ``move_cursor`` and ``move_cursor_no_end`` attributes
    pointing to callables that move the cursor to the given position.  The
    ``move_cursor_no_end`` method is used for motions that should not place the
    cursor at the end of a line.
    """

    move_cursor: Callable[[int], None]
    move_cursor_no_end: Callable[[int], None]

    # ------------------------------------------------------------------
    # Generic commands shared by normal, visual and vline executors
    # ------------------------------------------------------------------
    def colon(self, num: int = 1, num_str: str = ""):
        """Enter ``:`` command-line mode."""
        self.vim_status.set_message("")
        return RETURN_EXECUTOR_METHOD_INFO(self.executor_colon, False)

    # ------------------------------------------------------------------
    # Basic cursor movement commands shared by multiple executors
    # ------------------------------------------------------------------
    def zero(self, num: int = 1, num_str: str = ""):
        """Move to the first column of the current line."""
        motion_info = self.helper_motion.zero()
        self.move_cursor(motion_info.cursor_pos)

    def h(self, num: int = 1, num_str: str = ""):
        """Move cursor left."""
        motion_info = self.helper_motion.h(num=num)
        self.move_cursor(motion_info.cursor_pos)

    def j(self, num: int = 1, num_str: str = ""):
        """Move cursor down."""
        motion_info = self.helper_motion.j(num=num)
        self.move_cursor(motion_info.cursor_pos)

    def k(self, num: int = 1, num_str: str = ""):
        """Move cursor up."""
        motion_info = self.helper_motion.k(num=num)
        self.move_cursor(motion_info.cursor_pos)

    def l(self, num: int = 1, num_str: str = ""):
        """Move cursor right."""
        motion_info = self.helper_motion.l(num=num)
        self.move_cursor_no_end(motion_info.cursor_pos)

    def H(self, num: int = 1, num_str: str = ""):
        """Move cursor to the top of the page."""
        motion_info = self.helper_motion.H(num=num)
        self.move_cursor(motion_info.cursor_pos)

    def M(self, num: int = 1, num_str: str = ""):
        """Move cursor to the middle of the page."""
        motion_info = self.helper_motion.M(num=num)
        self.move_cursor(motion_info.cursor_pos)

    def L(self, num: int = 1, num_str: str = ""):
        """Move cursor to the bottom of the page."""
        motion_info = self.helper_motion.L(num=num)
        self.move_cursor(motion_info.cursor_pos)

    def caret(self, num: int = 1, num_str: str = ""):
        """Move to the first non-blank character of the line."""
        motion_info = self.helper_motion.caret(num=num)
        self.move_cursor(motion_info.cursor_pos)

    def dollar(self, num: int = 1, num_str: str = ""):
        """Move cursor to the end of the line."""
        motion_info = self.helper_motion.dollar(num=num)
        self.move_cursor_no_end(motion_info.cursor_pos)

    def w(self, num: int = 1, num_str: str = ""):
        """Move to the next word."""
        motion_info = self.helper_motion.w(num=num)
        self.move_cursor_no_end(motion_info.cursor_pos)

    def W(self, num: int = 1, num_str: str = ""):
        """Move to the next WORD."""
        motion_info = self.helper_motion.W(num=num)
        self.move_cursor_no_end(motion_info.cursor_pos)

    def b(self, num: int = 1, num_str: str = ""):
        """Move to the previous word."""
        motion_info = self.helper_motion.b(num=num)
        self.move_cursor(motion_info.cursor_pos)

    def B(self, num: int = 1, num_str: str = ""):
        """Move to the previous WORD."""
        motion_info = self.helper_motion.B(num=num)
        self.move_cursor(motion_info.cursor_pos)

    def e(self, num: int = 1, num_str: str = ""):
        """Move to the end of the current word."""
        motion_info = self.helper_motion.e(num=num)
        self.move_cursor(motion_info.cursor_pos)

    def percent(self, num: int = 1, num_str: str = ""):
        """Go to the matching bracket."""
        motion_info = self.helper_motion.percent(num=num, num_str=num_str)
        self.move_cursor(motion_info.cursor_pos)

    def semicolon(self, num: int = 1, num_str: str = ""):
        """Repeat the last f/t search."""
        motion_info = self.helper_motion.semicolon(num=num, num_str=num_str)
        self.move_cursor(motion_info.cursor_pos)

    def comma(self, num: int = 1, num_str: str = ""):
        """Repeat the last f/t search in opposite direction."""
        motion_info = self.helper_motion.comma(num=num, num_str=num_str)
        self.move_cursor(motion_info.cursor_pos)

    def space(self, num: int = 1, num_str: str = ""):
        """Move cursor right (space key)."""
        motion_info = self.helper_motion.space(num=num)
        self.move_cursor_no_end(motion_info.cursor_pos)

    def backspace(self, num: int = 1, num_str: str = ""):
        """Move cursor left (backspace key)."""
        motion_info = self.helper_motion.backspace(num=num)
        self.move_cursor_no_end(motion_info.cursor_pos)

    def enter(self, num: int = 1, num_str: str = ""):
        """Move cursor down (enter key)."""
        motion_info = self.helper_motion.enter(num=num)
        self.move_cursor(motion_info.cursor_pos)


class SelectionMixin:
    """Common operations for visual and block-visual executors."""

    # Hooks provided by subclasses
    apply_motion_info_in_sel: Callable[[object], None]
    set_cursor_pos_in_sel: Callable[[int], None]
    paste_in_sel: Callable[[int], None]

    # ------------------------------------------------------------------
    # Selection manipulation helpers
    # ------------------------------------------------------------------
    def r(self, num: int = 1, num_str: str = ""):
        """Replace selection with a typed character."""
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

    def greater(self, num: int = 1, num_str: str = ""):
        """Indent the selected text."""
        sel_start = self.get_pos_start_in_selection()
        sel_end = self.get_pos_end_in_selection()
        self.helper_action._indent(sel_start, sel_end)
        self.vim_status.to_normal()
        self.vim_status.cursor.draw_vim_cursor()

    def less(self, num: int = 1, num_str: str = ""):
        """Unindent the selected text."""
        sel_start = self.get_pos_start_in_selection()
        sel_end = self.get_pos_end_in_selection()
        self.helper_action._unindent(sel_start, sel_end)
        self.vim_status.to_normal()
        self.vim_status.cursor.draw_vim_cursor()

    def quote(self, num: int = 1, num_str: str = ""):
        """Switch register name."""
        executor_sub = self.executor_sub_register
        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred([])
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def x(self, num: int = 1, num_str: str = ""):
        """Alias for ``d``."""
        self.d(num, num_str)

    def c(self, num: int = 1, num_str: str = ""):
        """Delete selection and enter insert mode."""
        sel_start, _ = self.helper_action.yank(None)
        self.helper_action.delete(None, is_insert=True)
        self.vim_status.to_normal()
        self.set_cursor_pos(sel_start)
        self.get_editor().setFocus()

    def s(self, num: int = 1, num_str: str = ""):
        """Replace selection using sneak if enabled."""
        use_sneak = CONF.get(CONF_SECTION, "use_sneak")
        if use_sneak:
            executor_sub = self.executor_sub_sneak
            self.set_parent_info_to_submode(executor_sub, num, num_str)
            executor_sub.set_func_list_deferred(
                [
                    FUNC_INFO(self.apply_motion_info_in_sel, True),
                    FUNC_INFO(
                        self.helper_motion.display_another_group_after_sneak, False
                    ),
                ]
            )
            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)
        else:
            self.c(num, num_str)

    def y(self, num: int = 1, num_str: str = ""):
        """Yank selection into register."""
        sel_start, _ = self.helper_action.yank(None, is_explicit=True)
        self.vim_status.to_normal()
        self.set_cursor_pos(sel_start)

    def slash(self, num: int = 1, num_str: str = ""):
        """Enter search submode and execute motion on return."""
        self.vim_status.set_message("")
        executor_sub = self.executor_sub_search
        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_sel, True)]
        )
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, False)

    def n(self, num: int = 1, num_str: str = ""):
        """Jump to next search occurrence."""
        motion_info = self.helper_motion.n(num=num, num_str=num_str)
        self.set_cursor_pos_in_sel(motion_info.cursor_pos)

    def N(self, num: int = 1, num_str: str = ""):
        """Jump to previous search occurrence."""
        motion_info = self.helper_motion.N(num=num, num_str=num_str)
        self.set_cursor_pos_in_sel(motion_info.cursor_pos)

    def o(self, num: int = 1, num_str: str = ""):
        """Move cursor to the opposite end of the selection."""
        sel_start = self.vim_status.get_pos_start_in_selection()
        sel_end = self.vim_status.get_pos_end_in_selection()
        cur_pos = self.get_cursor().position()
        new_pos = (
            sel_end - 1
            if abs(sel_start - cur_pos) < abs(sel_end - cur_pos)
            else sel_start
        )
        self.set_cursor_pos(new_pos)

    def u(self, num: int = 1, num_str: str = ""):
        """Lowercase selected text."""
        self.helper_action.handle_case(None, "lower")

    def U(self, num: int = 1, num_str: str = ""):
        """Uppercase selected text."""
        self.helper_action.handle_case(None, "upper")

    def p(self, num: int = 1, num_str: str = ""):
        """Paste contents of register over the selection."""
        self.paste_in_sel(num)

    def P(self, num: int = 1, num_str: str = ""):
        """Paste contents of register over the selection."""
        self.paste_in_sel(num)

    def m(self, num: int = 1, num_str: str = ""):
        """Set a bookmark name."""
        executor_sub = self.executor_sub_alnum
        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.vim_status.set_bookmark, True)]
        )
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def apostrophe(self, num: int = 1, num_str: str = ""):
        """Jump to a bookmark linewise and keep selection."""
        executor_sub = self.executor_sub_alnum
        self.set_parent_info_to_submode(executor_sub, num, num_str)

        def run(ch: str):
            if ch.isupper():
                cur = self.vim_status.get_editorstack().get_current_filename()
                self.vim_status.jump_to_bookmark(ch)
                new = self.vim_status.get_editorstack().get_current_filename()
                if cur == new:
                    cursor = self.get_cursor()
                    self.set_cursor_pos_in_sel(cursor.block().position())
                else:
                    cursor = self.get_cursor()
                    self.set_cursor_pos(cursor.block().position())
                    self.vim_status.to_normal()
            else:
                info = self.helper_motion.apostrophe(ch)
                if info.cursor_pos is not None:
                    self.set_cursor_pos_in_sel(info.cursor_pos)

        executor_sub.set_func_list_deferred([FUNC_INFO(run, True)])
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def backtick(self, num: int = 1, num_str: str = ""):
        """Jump to a bookmark charwise and keep selection."""
        executor_sub = self.executor_sub_alnum
        self.set_parent_info_to_submode(executor_sub, num, num_str)

        def run(ch: str):
            if ch.isupper():
                cur = self.vim_status.get_editorstack().get_current_filename()
                self.vim_status.jump_to_bookmark(ch)
                new = self.vim_status.get_editorstack().get_current_filename()
                if cur != new:
                    self.vim_status.to_normal()
            else:
                info = self.helper_motion.backtick(ch)
                if info.cursor_pos is not None:
                    self.set_cursor_pos_in_sel(info.cursor_pos)

        executor_sub.set_func_list_deferred([FUNC_INFO(run, True)])
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def run_easymotion(self, num: int = 1, num_str: str = ""):
        """Invoke the EasyMotion submode."""
        executor_sub = self.executor_sub_easymotion
        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_sel, True)]
        )
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def asterisk(self, num: int = 1, num_str: str = ""):
        """Search forward for word under the cursor."""
        motion_info = self.helper_motion.asterisk(num)
        self.apply_motion_info_in_sel(motion_info)

    def sharp(self, num: int = 1, num_str: str = ""):
        """Search backward for word under the cursor."""
        motion_info = self.helper_motion.sharp(num)
        self.apply_motion_info_in_sel(motion_info)
