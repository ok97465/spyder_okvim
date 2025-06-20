# -*- coding: utf-8 -*-
"""Mixin classes used by command executors."""

from typing import Callable

from spyder_okvim.executor.executor_base import RETURN_EXECUTOR_METHOD_INFO


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
