# -*- coding: utf-8 -*-
"""Mixin classes used by command executors."""

# Standard Libraries
from typing import Callable

# Project Libraries
from spyder_okvim.executor.executor_base import DeferredAction, ExecutorTransition
from spyder_okvim.utils.motion import MotionInfo, MotionType
from spyder_okvim.vim.state import VimState


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
    def colon(self, count: int = 1, count_text: str = ""):
        """Enter Ex mode, fixing a Visual selection to numeric line addresses."""
        vs = self.vim_status
        vs.set_message("")
        self.executor_colon.pending_range_text = None
        if vs.vim_state in (VimState.VISUAL, VimState.VLINE):
            editor = self.get_editor()
            selections = editor.get_extra_selections("vim_selection")
            if selections:
                selection = selections[0].cursor
                start = selection.selectionStart()
                end = selection.selectionEnd()
                # Character selections are half-open. Line selections end at
                # the last block's end and can include its final empty block.
                if vs.vim_state == VimState.VISUAL and end > start:
                    end -= 1
                document = editor.document()
                first = document.findBlock(start).blockNumber() + 1
                last = document.findBlock(end).blockNumber() + 1
                self.executor_colon.pending_range_text = f":{first},{last}"
            vs.to_normal()
        return ExecutorTransition(self.executor_colon, False)

    # ------------------------------------------------------------------
    # Basic cursor movement commands shared by multiple executors
    # ------------------------------------------------------------------
    def zero(self, count: int = 1, count_text: str = ""):
        """Move to the first column of the current line."""
        motion_info = self.motions.zero()
        self.move_cursor(motion_info.cursor_pos)

    def h(self, count: int = 1, count_text: str = ""):
        """Move cursor left."""
        motion_info = self.motions.h(count=count)
        self.move_cursor(motion_info.cursor_pos)

    def j(self, count: int = 1, count_text: str = ""):
        """Move cursor down."""
        motion_info = self.motions.j(count=count)
        self.move_cursor(motion_info.cursor_pos)

    def k(self, count: int = 1, count_text: str = ""):
        """Move cursor up."""
        motion_info = self.motions.k(count=count)
        self.move_cursor(motion_info.cursor_pos)

    def l(self, count: int = 1, count_text: str = ""):
        """Move cursor right."""
        motion_info = self.motions.l(count=count)
        self.move_cursor_no_end(motion_info.cursor_pos)

    def H(self, count: int = 1, count_text: str = ""):
        """Move cursor to the top of the page."""
        motion_info = self.motions.H(count=count)
        self.move_cursor(motion_info.cursor_pos)

    def M(self, count: int = 1, count_text: str = ""):
        """Move cursor to the middle of the page."""
        motion_info = self.motions.M(count=count)
        self.move_cursor(motion_info.cursor_pos)

    def L(self, count: int = 1, count_text: str = ""):
        """Move cursor to the bottom of the page."""
        motion_info = self.motions.L(count=count)
        self.move_cursor(motion_info.cursor_pos)

    def caret(self, count: int = 1, count_text: str = ""):
        """Move to the first non-blank character of the line."""
        motion_info = self.motions.caret(count=count)
        self.move_cursor(motion_info.cursor_pos)

    def dollar(self, count: int = 1, count_text: str = ""):
        """Move cursor to the end of the line."""
        motion_info = self.motions.dollar(count=count)
        self.move_cursor_no_end(motion_info.cursor_pos)

    def w(self, count: int = 1, count_text: str = ""):
        """Move to the next word."""
        motion_info = self.motions.w(count=count)
        self.move_cursor_no_end(motion_info.cursor_pos)

    def W(self, count: int = 1, count_text: str = ""):
        """Move to the next WORD."""
        motion_info = self.motions.W(count=count)
        self.move_cursor_no_end(motion_info.cursor_pos)

    def b(self, count: int = 1, count_text: str = ""):
        """Move to the previous word."""
        motion_info = self.motions.b(count=count)
        self.move_cursor(motion_info.cursor_pos)

    def B(self, count: int = 1, count_text: str = ""):
        """Move to the previous WORD."""
        motion_info = self.motions.B(count=count)
        self.move_cursor(motion_info.cursor_pos)

    def e(self, count: int = 1, count_text: str = ""):
        """Move to the end of the current word."""
        motion_info = self.motions.e(count=count)
        self.move_cursor(motion_info.cursor_pos)

    def percent(self, count: int = 1, count_text: str = ""):
        """Go to the matching bracket."""
        motion_info = self.motions.percent(count=count, count_text=count_text)
        self.move_cursor(motion_info.cursor_pos)

    def semicolon(self, count: int = 1, count_text: str = ""):
        """Repeat the last f/t search."""
        motion_info = self.motions.semicolon(count=count, count_text=count_text)
        self.move_cursor(motion_info.cursor_pos)

    def comma(self, count: int = 1, count_text: str = ""):
        """Repeat the last f/t search in opposite direction."""
        motion_info = self.motions.comma(count=count, count_text=count_text)
        self.move_cursor(motion_info.cursor_pos)

    def space(self, count: int = 1, count_text: str = ""):
        """Move cursor right (space key)."""
        motion_info = self.motions.space(count=count)
        self.move_cursor_no_end(motion_info.cursor_pos)

    def backspace(self, count: int = 1, count_text: str = ""):
        """Move cursor left (backspace key)."""
        motion_info = self.motions.backspace(count=count)
        self.move_cursor_no_end(motion_info.cursor_pos)

    def enter(self, count: int = 1, count_text: str = ""):
        """Move cursor down (enter key)."""
        motion_info = self.motions.enter(count=count)
        self.move_cursor(motion_info.cursor_pos)


class SelectionMixin:
    """Common operations for characterwise and linewise Visual executors."""

    # Hooks provided by subclasses
    apply_motion_info_in_sel: Callable[[object], None]
    set_cursor_pos_in_sel: Callable[[int], None]

    # ------------------------------------------------------------------
    # Selection manipulation helpers
    # ------------------------------------------------------------------
    def select_text_object(self, motion_info: MotionInfo):
        """Apply a text object's range using its character/line selection mode."""
        if motion_info.motion_type == MotionType.LineWise:
            self.vim_status.to_visual_line()
        elif self.vim_status.vim_state == VimState.VLINE:
            self.vim_status.to_visual_char()
        self.vim_status.cursor.set_block_selection_in_visual(motion_info)

    def i(self, count: int = 1, count_text: str = ""):
        """Select an inner text object."""
        executor_sub = self.submodes.inner_text_object
        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred(
            [DeferredAction(self.select_text_object, True)]
        )
        return ExecutorTransition(executor_sub, True)

    def a(self, count: int = 1, count_text: str = ""):
        """Select a text object with its surroundings."""
        executor_sub = self.submodes.around_text_object
        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred(
            [DeferredAction(self.select_text_object, True)]
        )
        return ExecutorTransition(executor_sub, True)

    def r(self, count: int = 1, count_text: str = ""):
        """Replace selection with a typed character."""
        executor_sub = self.submodes.replace_character
        executor_sub.pos_start = self.get_pos_start_in_selection()
        executor_sub.pos_end = self.get_pos_end_in_selection()

        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred(
            [
                DeferredAction(self.vim_status.to_normal, False),
                DeferredAction(
                    lambda: self.set_cursor_pos(executor_sub.pos_start), False
                ),
            ]
        )

        return ExecutorTransition(executor_sub, True)

    def greater(self, count: int = 1, count_text: str = ""):
        """Indent the selected text."""
        self.edits.indent(None)
        self.vim_status.to_normal()
        self.vim_status.cursor.draw_vim_cursor()

    def less(self, count: int = 1, count_text: str = ""):
        """Unindent the selected text."""
        self.edits.unindent(None)
        self.vim_status.to_normal()
        self.vim_status.cursor.draw_vim_cursor()

    def quote(self, count: int = 1, count_text: str = ""):
        """Switch register name."""
        executor_sub = self.submodes.register_prefix
        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred([])
        return ExecutorTransition(executor_sub, True)

    def x(self, count: int = 1, count_text: str = ""):
        """Alias for ``d``."""
        self.d(count, count_text)

    def c(self, count: int = 1, count_text: str = ""):
        """Delete selection and enter insert mode."""
        sel_start, _ = self.edits.yank(None)
        self.edits.delete(None, is_insert=True)
        self.vim_status.to_normal()
        self.set_cursor_pos(sel_start)
        self.get_editor().setFocus()

    def s(self, count: int = 1, count_text: str = ""):
        """Replace selection using leap if enabled."""
        use_leap = self.vim_status.settings.use_leap
        if use_leap:
            executor_sub = self.submodes.leap_input
            executor_sub.begin()
            self.set_parent_info_to_submode(executor_sub, count, count_text)
            executor_sub.set_func_list_deferred(
                [DeferredAction(self.apply_motion_info_in_sel, True)]
            )
            return ExecutorTransition(executor_sub, True)
        else:
            self.c(count, count_text)

    def y(self, count: int = 1, count_text: str = ""):
        """Yank selection into register."""
        sel_start, _ = self.edits.yank(None, is_explicit=True)
        self.vim_status.to_normal()
        self.set_cursor_pos(sel_start)

    def slash(self, count: int = 1, count_text: str = "", forward: bool = True):
        """Enter search submode and execute motion on return."""
        self.vim_status.set_message("")
        executor_sub = self.submodes.search_prompt
        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred(
            [DeferredAction(self.apply_motion_info_in_sel, True)]
        )
        if not executor_sub.begin(forward):
            return
        return ExecutorTransition(executor_sub, False)

    def question(self, count: int = 1, count_text: str = ""):
        """Enter backward search while retaining the selection anchor."""
        return self.slash(count, count_text, forward=False)

    def n(self, count: int = 1, count_text: str = ""):
        """Jump to next search occurrence."""
        motion_info = self.motions.n(count=count, count_text=count_text)
        self.set_cursor_pos_in_sel(motion_info.cursor_pos)

    def N(self, count: int = 1, count_text: str = ""):
        """Jump to previous search occurrence."""
        motion_info = self.motions.N(count=count, count_text=count_text)
        self.set_cursor_pos_in_sel(motion_info.cursor_pos)

    def o(self, count: int = 1, count_text: str = ""):
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

    def u(self, count: int = 1, count_text: str = ""):
        """Lowercase selected text."""
        self.edits.change_case(None, "lower")

    def U(self, count: int = 1, count_text: str = ""):
        """Uppercase selected text."""
        self.edits.change_case(None, "upper")

    def p(self, count: int = 1, count_text: str = ""):
        """Paste contents of register over the selection."""
        self.vim_status.put_controller.put(count)

    P = p

    def m(self, count: int = 1, count_text: str = ""):
        """Set a bookmark name."""
        executor_sub = self.submodes.mark_name
        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred(
            [DeferredAction(self.vim_status.bookmark_manager.set_bookmark, True)]
        )
        return ExecutorTransition(executor_sub, True)

    def apostrophe(self, count: int = 1, count_text: str = ""):
        """Jump to a bookmark linewise and keep selection."""
        executor_sub = self.submodes.mark_name
        self.set_parent_info_to_submode(executor_sub, count, count_text)

        def run(ch: str):
            if ch.isupper():
                cur = self.vim_status.get_editorstack().get_current_filename()
                self.vim_status.bookmark_manager.jump_to_bookmark(ch)
                new = self.vim_status.get_editorstack().get_current_filename()
                if cur == new:
                    cursor = self.get_cursor()
                    self.set_cursor_pos_in_sel(cursor.block().position())
                else:
                    cursor = self.get_cursor()
                    self.set_cursor_pos(cursor.block().position())
                    self.vim_status.to_normal()
            else:
                info = self.motions.apostrophe(ch)
                if info.cursor_pos is not None:
                    self.set_cursor_pos_in_sel(info.cursor_pos)

        executor_sub.set_func_list_deferred([DeferredAction(run, True)])
        return ExecutorTransition(executor_sub, True)

    def backtick(self, count: int = 1, count_text: str = ""):
        """Jump to a bookmark charwise and keep selection."""
        executor_sub = self.submodes.mark_name
        self.set_parent_info_to_submode(executor_sub, count, count_text)

        def run(ch: str):
            if ch.isupper():
                cur = self.vim_status.get_editorstack().get_current_filename()
                self.vim_status.bookmark_manager.jump_to_bookmark(ch)
                new = self.vim_status.get_editorstack().get_current_filename()
                if cur != new:
                    self.vim_status.to_normal()
            else:
                info = self.motions.backtick(ch)
                if info.cursor_pos is not None:
                    self.set_cursor_pos_in_sel(info.cursor_pos)

        executor_sub.set_func_list_deferred([DeferredAction(run, True)])
        return ExecutorTransition(executor_sub, True)

    def run_easymotion(self, count: int = 1, count_text: str = ""):
        """Invoke the EasyMotion submode."""
        executor_sub = self.submodes.easymotion
        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred(
            [DeferredAction(self.apply_motion_info_in_sel, True)]
        )
        return ExecutorTransition(executor_sub, True)

    def asterisk(self, count: int = 1, count_text: str = ""):
        """Search forward for word under the cursor."""
        motion_info = self.motions.asterisk(count)
        self.apply_motion_info_in_sel(motion_info)

    def sharp(self, count: int = 1, count_text: str = ""):
        """Search backward for word under the cursor."""
        motion_info = self.motions.sharp(count)
        self.apply_motion_info_in_sel(motion_info)
