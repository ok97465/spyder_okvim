# -*- coding: utf-8 -*-
"""Cursor movement helpers for Vim emulation."""

# Standard Libraries
import ast
import re
from bisect import bisect_left, bisect_right

# Third Party Libraries
from qtpy.QtCore import QPoint, QRegularExpression
from qtpy.QtGui import QTextCursor, QTextDocument
from qtpy.QtWidgets import QTextEdit
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.utils.motion import MotionInfo, MotionType
from spyder_okvim.utils.search_helpers import SearchHelper
from spyder_okvim.utils.text_constants import BRACKET_PAIR

WHITE_SPACE = " \t"


class MotionHelper:
    """Utilities for computing cursor motions."""

    def __init__(self, vim_status):
        """Create helper bound to the given Vim status object.

        Args:
            vim_status: Object providing editor utilities.
        """
        self.vim_status = vim_status
        self.get_editor = vim_status.get_editor
        self.get_cursor = vim_status.get_cursor
        self.set_cursor = vim_status.set_cursor
        self.set_cursor_pos = vim_status.cursor.set_cursor_pos

        self.search_helper = SearchHelper(vim_status, self._set_motion_info)

        self.find_cmd_map = {
            "f": self.find_ch,
            "F": self.rfind_ch,
            "t": self.t,
            "T": self.T,
            "s": self.search_helper.sneak,
            "S": self.search_helper.rsneak,
            "z": self.search_helper.sneak,
            "Z": self.search_helper.rsneak,
        }

    def _set_motion_info(
        self,
        cur_pos: int | None,
        sel_start: int | None = None,
        sel_end: int | None = None,
        motion_type: int = MotionType.LineWise,
    ):
        """Build a :class:`MotionInfo` object.

        Args:
            cur_pos: The resulting cursor position.
            sel_start: Selection start position.
            sel_end: Selection end position.
            motion_type: Type of the motion.

        Returns:
            MotionInfo: Computed motion information.
        """
        return MotionInfo(
            cursor_pos=cur_pos,
            sel_start=sel_start,
            sel_end=sel_end,
            motion_type=motion_type,
        )

    def _get_ch(self, pos):
        """Get character of position."""
        if pos >= self.vim_status.cursor.get_end_position():
            return ""
        cursor = self.get_cursor()
        cursor.setPosition(pos)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
        return cursor.selectedText()

    def _get_leading_ch(self, pos):
        """Get character of position - 1."""
        cursor = self.get_cursor()
        cursor.setPosition(pos)
        cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor)
        return cursor.selectedText()

    def zero(self, num=1, num_str=""):
        """Get the start position of the current line."""
        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.StartOfLine)
        return self._set_motion_info(cursor.position(), motion_type=MotionType.CharWise)

    def l(self, num=1, num_str=""):
        """Get the position on the right side of the cursor."""
        cursor = self.get_cursor()
        pos_cur = cursor.position()

        if cursor.atBlockStart() and cursor.atBlockEnd():
            return self._set_motion_info(pos_cur, motion_type=MotionType.CharWise)

        cursor.movePosition(QTextCursor.EndOfBlock)
        pos_end = cursor.position()

        pos_new = pos_cur + num
        if pos_new > pos_end:
            pos_new = pos_end

        return self._set_motion_info(pos_new, motion_type=MotionType.CharWise)

    def h(self, num=1, num_str=""):
        """Get the position on the left side of the cursor."""
        cursor = self.get_cursor()
        pos_cur = cursor.position()

        if cursor.atBlockStart() and cursor.atBlockEnd():
            return self._set_motion_info(pos_cur, motion_type=MotionType.CharWise)

        cursor.movePosition(QTextCursor.StartOfBlock)
        pos_start = cursor.position()

        pos_new = pos_cur - num
        if pos_new < pos_start:
            pos_new = pos_start

        return self._set_motion_info(pos_new, motion_type=MotionType.CharWise)

    def k(self, num=1, num_str=""):
        """Get the position above the cursor."""
        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.Up, n=num)
        pos_new = cursor.position()
        if cursor.atBlockEnd() and not cursor.atBlockStart():
            pos_new -= 1

        return self._set_motion_info(pos_new)

    def j(self, num=1, num_str=""):
        """Get the position below the cursor."""
        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.Down, n=num)
        pos_new = cursor.position()
        if cursor.atBlockEnd() and not cursor.atBlockStart():
            pos_new -= 1

        return self._set_motion_info(pos_new)

    def H(self, num=1, num_str=""):
        """Get the position of the top of page."""
        editor = self.get_editor()
        pos = editor.cursorForPosition(QPoint(0, 0)).position()
        return self._set_motion_info(pos)

    def M(self, num=1, num_str=""):
        """Get the position of the middle of page."""
        editor = self.get_editor()
        qpos_mid = int(editor.viewport().height() * 0.5)
        block = editor.cursorForPosition(QPoint(0, qpos_mid)).block()
        return self._set_motion_info(block.position())

    def L(self, num=1, num_str=""):
        """Get the position of the bottom of page."""
        editor = self.get_editor()
        qpos_mid = int(editor.viewport().height())
        block = editor.cursorForPosition(QPoint(0, qpos_mid)).block()
        return self._set_motion_info(block.position())

    def dollar(self, num=1, num_str=""):
        """Get the position of the end of the current line."""
        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.EndOfLine, n=num)
        pos_new = cursor.position()

        return self._set_motion_info(pos_new, motion_type=MotionType.CharWise)

    def caret(self, num=1, num_str=""):
        """Get the position of the first non-blank character of the line."""
        cursor = self.get_cursor()
        block = cursor.block()
        text = block.text()
        pos = cursor.position()
        if text.strip():
            start_of_line = len(text) - len(text.lstrip())
            pos = block.position() + start_of_line

        return self._set_motion_info(pos, motion_type=MotionType.CharWise)

    def w(self, num=1, num_str=""):
        """Get the position of the next word."""
        cursor = self.get_cursor()
        for _ in range(num):
            cursor.movePosition(QTextCursor.NextWord)
            if cursor.atBlockEnd():
                cursor.movePosition(QTextCursor.NextWord)
                if self._get_ch(cursor.position()) in WHITE_SPACE:
                    cursor.movePosition(QTextCursor.NextWord)

        return self._set_motion_info(cursor.position(), motion_type=MotionType.CharWise)

    def w_for_d(self, num=1, num_str=""):
        """Get the position of the next word in d command."""
        cursor = self.get_cursor()
        for _ in range(num):
            if cursor.atBlockEnd():
                cursor.movePosition(QTextCursor.NextWord)
                if self._get_ch(cursor.position()) in WHITE_SPACE:
                    cursor.movePosition(QTextCursor.NextWord, n=2)
                else:
                    cursor.movePosition(QTextCursor.NextWord)
            else:
                cursor.movePosition(QTextCursor.NextWord)

        return self._set_motion_info(cursor.position(), motion_type=MotionType.CharWise)

    def w_for_c(self, num=1, num_str=""):
        """Get the position of the next word for c command."""
        cursor = self.get_cursor()
        for _ in range(num - 1):
            cursor.movePosition(QTextCursor.NextWord)
            if cursor.atBlockEnd():
                cursor.movePosition(QTextCursor.NextWord)
                if self._get_ch(cursor.position()) in WHITE_SPACE:
                    cursor.movePosition(QTextCursor.NextWord)

        if self._get_ch(cursor.position()) in WHITE_SPACE:
            cursor.movePosition(QTextCursor.NextWord)
        else:
            cursor.movePosition(QTextCursor.EndOfWord)

        return self._set_motion_info(cursor.position(), motion_type=MotionType.CharWise)

    def W(self, num=1, num_str=""):
        """Get the position of the next WORD."""
        cursor = self.get_cursor()
        for _ in range(num):
            if cursor.atBlockEnd():
                cursor.movePosition(QTextCursor.NextWord)
                if self._get_ch(cursor.position()) in WHITE_SPACE:
                    cursor.movePosition(QTextCursor.NextWord)
            else:
                cursor.movePosition(QTextCursor.NextWord)
                while self._get_leading_ch(cursor.position()) not in WHITE_SPACE:
                    if cursor.atBlockEnd():
                        cursor.movePosition(QTextCursor.NextWord)
                        if self._get_ch(cursor.position()) in WHITE_SPACE:
                            cursor.movePosition(QTextCursor.NextWord)
                        break
                    cursor.movePosition(QTextCursor.NextWord)

        return self._set_motion_info(cursor.position(), motion_type=MotionType.CharWise)

    def W_for_d(self, num=1, num_str=""):
        """Get the position of the next WORD."""
        cursor = self.get_cursor()
        for _ in range(num):
            if cursor.atBlockEnd():
                cursor.movePosition(QTextCursor.NextWord)
                if self._get_ch(cursor.position()) in WHITE_SPACE:
                    cursor.movePosition(QTextCursor.NextWord)

            cursor.movePosition(QTextCursor.NextWord)
            while self._get_leading_ch(cursor.position()) not in WHITE_SPACE:
                if cursor.atBlockEnd():
                    break
                cursor.movePosition(QTextCursor.NextWord)

        return self._set_motion_info(cursor.position(), motion_type=MotionType.CharWise)

    def W_for_c(self, num=1, num_str=""):
        """Get the position of the next WORD for c command."""
        cursor = self.get_cursor()
        for _ in range(num - 1):
            if cursor.atBlockEnd():
                cursor.movePosition(QTextCursor.NextWord)
                if self._get_ch(cursor.position()) in WHITE_SPACE:
                    cursor.movePosition(QTextCursor.NextWord)
            else:
                cursor.movePosition(QTextCursor.NextWord)
                while self._get_leading_ch(cursor.position()) not in WHITE_SPACE:
                    if cursor.atBlockEnd():
                        cursor.movePosition(QTextCursor.NextWord)
                        if self._get_ch(cursor.position()) in WHITE_SPACE:
                            cursor.movePosition(QTextCursor.NextWord)
                        break
                    cursor.movePosition(QTextCursor.NextWord)

        if self._get_ch(cursor.position()) in WHITE_SPACE:
            cursor.movePosition(QTextCursor.NextWord)
        else:
            cursor.movePosition(QTextCursor.EndOfWord)
            while (
                self._get_ch(cursor.position()) not in WHITE_SPACE
                and not cursor.atBlockEnd()
            ):
                cursor.movePosition(QTextCursor.Right)
                cursor.movePosition(QTextCursor.EndOfWord)

        return self._set_motion_info(cursor.position(), motion_type=MotionType.CharWise)

    def b(self, num=1, num_str=""):
        """Get the position of the previous word."""
        cursor = self.get_cursor()

        def move2previousword(_cursor):
            _cursor.movePosition(QTextCursor.PreviousWord)
            while (
                cursor.atBlockStart() and self._get_ch(cursor.position()) in WHITE_SPACE
            ):
                if _cursor.position() == 0:
                    break
                if _cursor.atBlockStart() and cursor.atBlockEnd():
                    break
                _cursor.movePosition(QTextCursor.PreviousWord)
            return _cursor

        for _ in range(num):
            cursor = move2previousword(cursor)
            while cursor.atBlockEnd() and not cursor.atBlockStart():
                cursor = move2previousword(cursor)

        return self._set_motion_info(cursor.position(), motion_type=MotionType.CharWise)

    def B(self, num=1, num_str=""):
        """Get the position of the previous WORD."""
        cursor = self.get_cursor()

        def move2previousWORD(_cursor):
            _cursor.movePosition(QTextCursor.PreviousWord)
            while self._get_leading_ch(cursor.position()) not in WHITE_SPACE:
                if _cursor.position() == 0:
                    break
                if _cursor.atBlockStart() and cursor.atBlockEnd():
                    break
                _cursor.movePosition(QTextCursor.PreviousWord)
            return _cursor

        for _ in range(num):
            cursor = move2previousWORD(cursor)
            while cursor.atBlockEnd() and not cursor.atBlockStart():
                cursor = move2previousWORD(cursor)

        return self._set_motion_info(cursor.position(), motion_type=MotionType.CharWise)

    def e(self, num=1, num_str=""):
        """Get the position of the end of word.

        Does not stop in an empty line.

        """
        cursor = self.get_cursor()
        pos_old = cursor.position()

        if not cursor.atBlockEnd():
            cursor.movePosition(QTextCursor.Right)

        def _helper_e(cursor):
            while (
                cursor.atBlockEnd()
                or not cursor.block().text().strip()
                or self._get_ch(cursor.position()) in WHITE_SPACE
            ):
                cursor.movePosition(QTextCursor.NextWord)
                if cursor.atEnd():
                    break

            cursor.movePosition(QTextCursor.EndOfWord)
            return cursor

        for _ in range(num):
            cursor = _helper_e(cursor)

        if pos_old < cursor.position():
            cursor.movePosition(QTextCursor.Left)

        return self._set_motion_info(
            cursor.position(), motion_type=MotionType.CharWiseIncludingEnd
        )

    def G(self, num=1, num_str=""):
        """Get the position of the Line.

        if num_str is False, this function return the last line position.

        """
        editor = self.get_editor()
        n_block = editor.blockCount()

        if num > n_block:
            cursor = self.get_cursor()
            return self._set_motion_info(cursor.position())

        if num_str:
            block = editor.document().findBlockByNumber(num - 1)
        else:
            block = editor.document().findBlockByNumber(n_block - 1)

        text = block.text()
        start_of_line = len(text) - len(text.lstrip())
        if not text.strip() and text:
            start_of_line -= 1
        pos = block.position() + start_of_line

        return self._set_motion_info(pos)

    def percent(self, num=1, num_str=""):
        """Get the position of matching bracket."""
        txt = self.get_editor().toPlainText()
        cursor_pos = self.get_cursor().position()
        pos_start = None
        pos_end = None

        for match in re.finditer(r"[\(\[\{\}\]\)]", txt[cursor_pos::]):
            pos_start = match.start()
            ch_start = match.group()
            if ch_start in ")]}":
                pos_start += cursor_pos
                sub_txt = reversed(txt[:pos_start])
            else:
                pos_start += cursor_pos + 1
                sub_txt = txt[pos_start::]
            break

        if pos_start is None:
            return self._set_motion_info(None)

        stack = [ch_start]

        for idx, ch in enumerate(sub_txt):
            if ch == BRACKET_PAIR.get(stack[-1], None):
                stack.pop()
            elif ch in "()[]{}":
                stack.append(ch)
            if not stack and (ch_start in "([{"):
                pos_end = pos_start + idx
                break
            elif not stack and (ch_start in "}])"):
                pos_end = pos_start - idx - 1
                break

        return self._set_motion_info(
            pos_end, motion_type=MotionType.CharWiseIncludingEnd
        )

    def find_ch(self, ch, num=1, by_repeat_cmd=False):
        """Get the position of the next occurrence of a character."""
        if by_repeat_cmd is False:
            self.vim_status.find_info.set("f", ch)
        cursor = self.get_cursor()
        block = cursor.block()
        search_pos = cursor.positionInBlock() + 1
        txt = block.text()
        ch_pos = -1
        for _ in range(num):
            ch_pos = txt.find(ch, search_pos)
            if ch_pos < 0:
                break
            search_pos = ch_pos + 1

        if ch_pos < 0:
            return self._set_motion_info(None, motion_type=MotionType.CharWise)
        else:
            return self._set_motion_info(
                ch_pos + block.position(), motion_type=MotionType.CharWiseIncludingEnd
            )

    def rfind_ch(self, ch, num=1, by_repeat_cmd=False):
        """Get the position of the previous occurrence of a character."""
        if by_repeat_cmd is False:
            self.vim_status.find_info.set("F", ch)
        cursor = self.get_cursor()
        block = cursor.block()
        search_pos = cursor.positionInBlock()
        txt = block.text()
        ch_pos = -1
        for _ in range(num):
            ch_pos = txt[:search_pos].rfind(ch)
            if ch_pos < 0:
                break
            search_pos = ch_pos

        if ch_pos < 0:
            return self._set_motion_info(None, motion_type=MotionType.CharWise)
        else:
            return self._set_motion_info(
                ch_pos + block.position(), motion_type=MotionType.CharWise
            )

    def t(self, ch, num=1, by_repeat_cmd=False):
        """Get the position - 1 of the next occurrence of a character."""
        if by_repeat_cmd is False:
            self.vim_status.find_info.set("t", ch)
        cursor = self.get_cursor()
        block = cursor.block()
        search_pos = cursor.positionInBlock() + 1
        txt = block.text()
        ch_pos = -1
        for idx in range(num):
            if num == 1 and by_repeat_cmd is True:
                search_pos += 1
            ch_pos = txt.find(ch, search_pos)
            if ch_pos < 0:
                break
            search_pos = ch_pos + 1

        ch_pos -= 1
        if ch_pos < 0:
            return self._set_motion_info(None, motion_type=MotionType.CharWise)
        else:
            return self._set_motion_info(
                ch_pos + block.position(), motion_type=MotionType.CharWiseIncludingEnd
            )

    def T(self, ch, num=1, by_repeat_cmd=False):
        """Get the position + 1 of the previous occurrence of a character."""
        if by_repeat_cmd is False:
            self.vim_status.find_info.set("T", ch)
        cursor = self.get_cursor()
        block = cursor.block()
        search_pos = cursor.positionInBlock()
        txt = block.text()
        ch_pos = -1
        for idx in range(num):
            if num == 1 and by_repeat_cmd is True:
                search_pos -= 1
                if search_pos == -1:
                    break
            ch_pos = txt[:search_pos].rfind(ch)
            if ch_pos < 0:
                break
            search_pos = ch_pos

        if ch_pos < 0:
            return self._set_motion_info(None, motion_type=MotionType.CharWise)

        ch_pos += 1
        if ch_pos >= block.length():
            return self._set_motion_info(None, motion_type=MotionType.CharWise)
        return self._set_motion_info(
            ch_pos + block.position(), motion_type=MotionType.CharWise
        )

    def get_cursor_pos_of_viewport(self) -> tuple[int, int]:
        """Return start and end positions of the visible viewport."""
        return self.search_helper.get_viewport_positions()

    def search_forward_in_view(self, txt: str) -> list[int]:
        """Return positions of ``txt`` within the visible viewport."""
        return self.search_helper.search_forward_in_view(txt)

    def sneak(self, ch2, num=1, by_repeat_cmd=False):
        """Delegate to :class:`SearchHelper`."""
        return self.search_helper.sneak(ch2, num, by_repeat_cmd)

    def display_another_group_after_sneak(self):
        """Show annotations for additional sneak targets."""
        self.search_helper.display_another_group_after_sneak()

    def search_backward_in_view(self, txt: str) -> list[int]:
        """Return positions of ``txt`` when searching backward in the viewport."""
        return self.search_helper.search_backward_in_view(txt)

    def rsneak(self, ch2, num=1, by_repeat_cmd=False):
        """Delegate to :class:`SearchHelper`."""
        return self.search_helper.rsneak(ch2, num, by_repeat_cmd)

    def display_another_group_after_rsneak(self):
        """Show annotations for additional reverse sneak targets."""
        self.search_helper.display_another_group_after_rsneak()

    def semicolon(self, num=1, num_str=""):
        """Repeat latest f, t, F or T."""
        name = self.vim_status.find_info.cmd_name
        ch = self.vim_status.find_info.ch
        method = self.find_cmd_map.get(name, None)
        if method is None:
            return self._set_motion_info(None, motion_type=MotionType.CharWise)
        motion_info = method(ch, num, True)
        return motion_info

    def comma(self, num=1, num_str=""):
        """Repeat latest f, t, F or T in opposite direction."""
        name = self.vim_status.find_info.cmd_name
        ch = self.vim_status.find_info.ch
        method = self.find_cmd_map.get(name.swapcase(), None)
        if method is None:
            return self._set_motion_info(None, motion_type=MotionType.CharWise)
        motion_info = method(ch, num, True)
        return motion_info

    def apostrophe(self, mark: str):
        """Return linewise position of mark."""
        info = self.vim_status.get_bookmark(mark)
        if not info:
            return self._set_motion_info(None)
        current = self.vim_status.get_editorstack().get_current_filename()
        if info.get("file") != current:
            return self._set_motion_info(None)
        editor = self.get_editor()
        block = editor.document().findBlockByNumber(info["line"])
        if not block.isValid():
            if mark.isupper():
                self.vim_status.bookmarks_global.pop(mark, None)
                self.vim_status._save_persistent_bookmarks()
            else:
                self.vim_status.bookmarks[current].pop(mark, None)
            return self._set_motion_info(None)
        return self._set_motion_info(block.position(), motion_type=MotionType.LineWise)

    def backtick(self, mark: str):
        """Return charwise position of mark."""
        info = self.vim_status.get_bookmark(mark)
        if not info:
            return self._set_motion_info(None)
        current = self.vim_status.get_editorstack().get_current_filename()
        if info.get("file") != current:
            return self._set_motion_info(None)
        editor = self.get_editor()
        block = editor.document().findBlockByNumber(info["line"])
        if not block.isValid():
            if mark.isupper():
                self.vim_status.bookmarks_global.pop(mark, None)
                self.vim_status._save_persistent_bookmarks()
            else:
                self.vim_status.bookmarks[current].pop(mark, None)
            return self._set_motion_info(None)
        pos = block.position() + min(info["col"], block.length() - 1)
        return self._set_motion_info(pos, motion_type=MotionType.CharWiseIncludingEnd)

    def i_quote(self, quote):
        """Find quoted block position excluding quotes."""
        sel_end = None

        cursor = self.get_cursor()
        block = cursor.block()
        text = block.text()

        cursor_pos = cursor.positionInBlock()
        if self._get_ch(cursor.position()) == quote:
            # When the cursor starts on a quote, Vim will figure out which
            # quote pairs form a string by searching from the start of the line
            quote_pos = [m.start() for m in re.finditer(quote, text[:cursor_pos])]
            if len(quote_pos) % 2 == 0:
                sel_start = cursor_pos
                sel_end = text.find(quote, cursor_pos + 1)
            else:
                sel_start = quote_pos[-1]
                sel_end = cursor_pos
        else:
            sel_start = text[:cursor_pos].rfind(quote)

            if sel_start < 0:
                sel_start = text.find(quote, cursor_pos)
                if sel_start < 0:
                    pass
                else:
                    sel_end = text.find(quote, sel_start + 1)
            else:
                sel_end = text.find(quote, cursor_pos)

        if sel_start > -1 and sel_end > -1:
            sel_start = sel_start + block.position() + 1
            sel_end = sel_end + block.position()
        else:
            sel_start = None
            sel_end = None

        return self._set_motion_info(
            None, sel_start, sel_end, motion_type=MotionType.BlockWise
        )

    def _include_trailing_white(self, pos_end):
        """Add the position of trailing white space."""
        cursor = self.get_cursor()

        cursor.setPosition(pos_end)

        # including trailing text
        if (
            pos_end < self.vim_status.cursor.get_end_position()
            and not cursor.atBlockEnd()
        ):
            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
            ch = cursor.selectedText()

            cursor.setPosition(pos_end)
            if ch in WHITE_SPACE:
                cursor.movePosition(QTextCursor.NextWord)
                pos_end = cursor.position()

        return pos_end

    def _include_leading_white(self, pos_start):
        """Add the position of leading white."""
        cursor = self.get_cursor()

        cursor.setPosition(pos_start)
        block = cursor.block()
        text = block.text()
        text = text[: pos_start - block.position()]

        pos_start -= len(text) - len(text.rstrip())

        return pos_start

    def a_quote(self, quote):
        """Find quoted block position including trailing white space."""
        sel_end = None

        cursor = self.get_cursor()
        block = cursor.block()
        text = block.text()

        cursor_pos = cursor.positionInBlock()
        if self._get_ch(cursor.position()) == quote:
            # When the cursor starts on a quote, Vim will figure out which
            # quote pairs form a string by searching from the start of the line
            quote_pos = [m.start() for m in re.finditer(quote, text[:cursor_pos])]
            if len(quote_pos) % 2 == 0:
                sel_start = cursor_pos
                sel_end = text.find(quote, cursor_pos + 1)
            else:
                sel_start = quote_pos[-1]
                sel_end = cursor_pos
        else:
            sel_start = text[:cursor_pos].rfind(quote)

            if sel_start < 0:
                sel_start = text.find(quote, cursor_pos)
                if sel_start < 0:
                    pass
                else:
                    sel_end = text.find(quote, sel_start + 1)
            else:
                sel_end = text.find(quote, cursor_pos)

        if sel_start > -1 and sel_end > -1:
            sel_start = sel_start + block.position()
            sel_end = sel_end + block.position() + 1
            sel_end_old = sel_end
            sel_end = self._include_trailing_white(sel_end)
            if sel_end == sel_end_old:
                sel_start = self._include_leading_white(sel_start)
        else:
            sel_start = None
            sel_end = None

        return self._set_motion_info(
            None, sel_start, sel_end, motion_type=MotionType.BlockWise
        )

    def i_w(self, num):
        """Find word block position."""
        cursor = self.get_cursor()

        sel_start_init = cursor.position()

        if self._get_ch(cursor.position()) in WHITE_SPACE:
            cursor_pos_in_block = cursor.positionInBlock()
            txt = cursor.block().text()
            txt_leading = txt[:cursor_pos_in_block]
            txt_trailing = txt[cursor_pos_in_block:]

            n_leading_space = len(txt_leading) - len(txt_leading.rstrip())
            n_trailing_space = len(txt_trailing) - len(txt_trailing.lstrip())
            sel_start = cursor_pos_in_block - n_leading_space
            sel_end = cursor_pos_in_block + n_trailing_space
            cursor.setPosition(sel_end + cursor.block().position())
            num -= 1
        else:
            cursor.movePosition(QTextCursor.EndOfWord)
            cursor.movePosition(QTextCursor.StartOfWord)

            # For "abc.dd" at 0 position of cursor
            if sel_start_init < cursor.position():
                cursor.movePosition(QTextCursor.Left)
                cursor.movePosition(QTextCursor.StartOfWord)

            sel_start = cursor.position()

        for idx in range(num):
            if idx % 2 == 0:
                cursor.movePosition(QTextCursor.EndOfWord)
            else:
                # go to the end of blank
                if cursor.atBlockEnd():
                    cursor.movePosition(QTextCursor.NextWord, n=2)
                else:
                    cursor.movePosition(QTextCursor.NextWord)

        sel_end = cursor.position()

        return self._set_motion_info(
            None, sel_start, sel_end, motion_type=MotionType.BlockWise
        )

    def i_W(self, num):
        """Find WORD block position."""
        cursor = self.get_cursor()

        if self._get_ch(cursor.position()) in WHITE_SPACE:
            cursor_pos_in_block = cursor.positionInBlock()
            txt = cursor.block().text()
            txt_leading = txt[:cursor_pos_in_block]
            txt_trailing = txt[cursor_pos_in_block:]

            n_leading_space = len(txt_leading) - len(txt_leading.rstrip())
            n_trailing_space = len(txt_trailing) - len(txt_trailing.lstrip())
            sel_start = cursor_pos_in_block - n_leading_space
            sel_end = cursor_pos_in_block + n_trailing_space
            cursor.setPosition(sel_end + cursor.block().position())
            num -= 1
        else:
            cursor.movePosition(QTextCursor.EndOfWord)
            cursor.movePosition(QTextCursor.StartOfWord)

            while (
                not cursor.atBlockStart()
                and self._get_leading_ch(cursor.position()) not in WHITE_SPACE
            ):
                cursor.movePosition(QTextCursor.Left)
                cursor.movePosition(QTextCursor.StartOfWord)

            sel_start = cursor.position()

        for idx in range(num):
            if idx % 2 == 0:
                if cursor.atBlockEnd():
                    cursor.movePosition(QTextCursor.NextWord, n=2)
                else:
                    cursor.movePosition(QTextCursor.EndOfWord)
                    while (
                        not cursor.atBlockEnd()
                        and self._get_ch(cursor.position()) not in WHITE_SPACE
                    ):
                        cursor.movePosition(QTextCursor.Right)
                        if self._get_ch(cursor.position()) not in WHITE_SPACE:
                            cursor.movePosition(QTextCursor.EndOfWord)
            else:
                # go to the end of blank
                if cursor.atBlockEnd():
                    cursor.movePosition(QTextCursor.NextWord, n=2)
                else:
                    cursor.movePosition(QTextCursor.NextWord)

        sel_end = cursor.position()

        return self._set_motion_info(
            None, sel_start, sel_end, motion_type=MotionType.BlockWise
        )

    def a_w(self, num):
        """Find word block position including white space."""
        cursor = self.get_cursor()

        sel_start_init = cursor.position()

        is_trailing_space = True

        if self._get_ch(cursor.position()) in WHITE_SPACE:
            cursor_pos_in_block = cursor.positionInBlock()
            txt = cursor.block().text()
            txt_leading = txt[:cursor_pos_in_block]

            n_leading_space = len(txt_leading) - len(txt_leading.rstrip())
            sel_start = cursor_pos_in_block - n_leading_space
            cursor.movePosition(QTextCursor.NextWord)
            cursor.movePosition(QTextCursor.EndOfWord)
            is_trailing_space = False
            num -= 1
        else:
            cursor.movePosition(QTextCursor.EndOfWord)
            cursor.movePosition(QTextCursor.StartOfWord)

            # For "abc.dd" at 0 position of cursor
            if sel_start_init < cursor.position():
                cursor.movePosition(QTextCursor.Left)
                cursor.movePosition(QTextCursor.StartOfWord)

            sel_start = cursor.position()

        if is_trailing_space:
            for idx in range(num):
                if cursor.atBlockEnd():
                    # TODO : Fix the case that the line has leading space.
                    cursor.movePosition(QTextCursor.NextWord, n=2)
                else:
                    cursor.movePosition(QTextCursor.NextWord)
        else:
            for idx in range(num):
                block = cursor.block()
                txt = block.text()
                if len(txt.rstrip()) == cursor.position() - block.position():
                    cursor.movePosition(QTextCursor.NextBlock)
                    cursor.movePosition(QTextCursor.StartOfLine)
                    if self._get_ch(cursor.position()) in WHITE_SPACE:
                        cursor.movePosition(QTextCursor.NextWord)
                    cursor.movePosition(QTextCursor.EndOfWord)
                else:
                    cursor.movePosition(QTextCursor.NextWord)
                    cursor.movePosition(QTextCursor.EndOfWord)

        sel_end = cursor.position()

        return self._set_motion_info(
            None, sel_start, sel_end, motion_type=MotionType.BlockWise
        )

    def get_pos_bracket(
        self, num: int, bracket: str, cursor_pos: int
    ) -> tuple[int | None, int | None]:
        """Get the position of the bracket block."""
        # Todo: apply num
        pair_bracket = {
            "(": ["(", ")", r"[()]"],
            ")": ["(", ")", r"[()]"],
            "[": ["[", "]", r"[\[\]]"],
            "]": ["[", "]", r"[\[\]]"],
            "{": ["{", "}", r"[{}]"],
            "}": ["{", "}", r"[{}]"],
        }
        b_open, b_close, pattern_str = pair_bracket[bracket]
        txt = self.get_editor().toPlainText()

        sel_start = None
        sel_end = None

        pattern = re.compile(pattern_str)

        # Find position of close bracket
        if self._get_ch(cursor_pos) == b_close:
            sel_end = cursor_pos + 1
        else:
            n_open = 0
            for match in pattern.finditer(txt[cursor_pos + 1 : :]):
                ch = match.group()
                if ch == b_open:
                    n_open += 1
                else:
                    if n_open > 0:
                        n_open -= 1
                    else:
                        sel_end = match.start() + cursor_pos + 1 + 1
                        break

        # Find position of open bracket
        if sel_end is None:
            pass
        elif self._get_ch(cursor_pos) == b_open:
            sel_start = cursor_pos
        else:
            n_close = 0
            for idx, ch in enumerate(reversed(txt[:cursor_pos])):
                if ch == b_close:
                    n_close += 1
                elif ch == b_open:
                    if n_close > 0:
                        n_close -= 1
                    else:
                        sel_start = cursor_pos - idx - 1
                        break

        if sel_start is None or sel_end is None:
            sel_start = None
            sel_end = None

        return sel_start, sel_end

    def a_bracket(self, num: int, bracket: str) -> MotionInfo:
        """Get the position of the bracket block."""
        cursor = self.get_cursor()
        cursor_pos = cursor.position()
        sel_start, sel_end = self.get_pos_bracket(num, bracket, cursor_pos)

        if sel_start is None:
            # There are an open bracket after the cursor on the same line.
            open_bracket = {"(": "(", ")": "(", "[": "[", "]": "[", "{": "{", "}": "{"}[
                bracket
            ]
            block = cursor.block()
            txt = block.text()
            block_pos = block.position()

            txt_right = txt[cursor_pos - block_pos :]
            open_bracket_pos = txt_right.find(open_bracket) + cursor_pos
            if open_bracket_pos > cursor_pos:
                sel_start, sel_end = self.get_pos_bracket(
                    num, bracket, open_bracket_pos
                )

        return self._set_motion_info(
            None, sel_start, sel_end, motion_type=MotionType.BlockWise
        )

    def i_bracket(self, num: int, bracket: str) -> MotionInfo:
        """Get the position of the bracket inner block."""
        motion_info = self.a_bracket(num, bracket)
        if motion_info.sel_start is not None and motion_info.sel_end is not None:
            motion_info.sel_start += 1
            motion_info.sel_end -= 1
            if motion_info.sel_start == motion_info.sel_end:
                motion_info.sel_start = None
                motion_info.sel_end = None

        return motion_info

    def search(self, txt: str):
        """Delegate search to :class:`SearchHelper`."""
        self.search_helper.search(txt)

    def n(self, num=1, num_str=""):
        """Move to the next search match."""
        return self.search_helper.n(num, num_str)

    def N(self, num=1, num_str=""):
        """Move to the previous search match."""
        return self.search_helper.N(num, num_str)

    def _get_word_under_cursor(self) -> str:
        """Return word under cursor."""
        editor = self.get_editor()
        return editor.get_current_word()

    def asterisk(self, num=1, num_str=""):
        """Search forward for the word under the cursor."""
        return self.search_helper.asterisk(num, num_str)

    def sharp(self, num=1, num_str=""):
        """Search backward for the word under the cursor."""
        return self.search_helper.sharp(num, num_str)

    def space(self, num=1, num_str=""):
        """Get the position on the right side of the cursor."""
        cursor = self.get_cursor()

        for _ in range(num):
            cursor.movePosition(QTextCursor.Right)
            if cursor.atBlockEnd():
                cursor.movePosition(QTextCursor.Right)

        return self._set_motion_info(cursor.position(), motion_type=MotionType.CharWise)

    def backspace(self, num=1, num_str=""):
        """Get the position on the right side of the cursor."""
        cursor = self.get_cursor()

        cursor.movePosition(QTextCursor.Left, n=num)

        return self._set_motion_info(cursor.position(), motion_type=MotionType.CharWise)

    def enter(self, num=1, num_str=""):
        """Get the position below the cursor."""
        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.Down, n=num)
        block = cursor.block()
        text = block.text()
        pos = cursor.position()

        if text.strip():
            start_of_line = len(text) - len(text.lstrip())
            pos = block.position() + start_of_line

        return self._set_motion_info(pos)

    def s(self, num):
        """Line block position."""
        cursor = self.get_cursor()

        sel_start_init = cursor.position()

        if self._get_ch(cursor.position()) in WHITE_SPACE:
            cursor_pos_in_block = cursor.positionInBlock()
            txt = cursor.block().text()
            txt_leading = txt[:cursor_pos_in_block]
            txt_trailing = txt[cursor_pos_in_block:]

            n_leading_space = len(txt_leading) - len(txt_leading.rstrip())
            n_trailing_space = len(txt_trailing) - len(txt_trailing.lstrip())
            sel_start = cursor_pos_in_block - n_leading_space
            sel_end = cursor_pos_in_block + n_trailing_space
            cursor.setPosition(sel_end + cursor.block().position())
            num -= 1
        else:
            cursor.movePosition(QTextCursor.EndOfWord)
            cursor.movePosition(QTextCursor.StartOfWord)

            # For "abc.dd" at 0 position of cursor
            if sel_start_init < cursor.position():
                cursor.movePosition(QTextCursor.Left)
                cursor.movePosition(QTextCursor.StartOfWord)

            sel_start = cursor.position()

        for idx in range(num):
            if idx % 2 == 0:
                cursor.movePosition(QTextCursor.EndOfWord)
            else:
                # go to the end of blank
                if cursor.atBlockEnd():
                    cursor.movePosition(QTextCursor.NextWord, n=2)
                else:
                    cursor.movePosition(QTextCursor.NextWord)

        sel_end = cursor.position()

        return self._set_motion_info(
            None, sel_start, sel_end, motion_type=MotionType.BlockWise
        )

    # ------------------------------------------------------------------
    # Python navigation helpers
    # ------------------------------------------------------------------
    def _get_python_definition_positions(self) -> list[int]:
        """Return character positions of Python class and function definitions."""
        editor = self.get_editor()
        text = editor.toPlainText()

        try:
            tree = ast.parse(text)
        except SyntaxError:
            return []

        lines: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                lines.add(node.lineno)

        positions: list[int] = []
        for line in sorted(lines):
            block = editor.document().findBlockByNumber(line - 1)
            if not block.isValid():
                continue
            txt = block.text()
            start_of_line = len(txt) - len(txt.lstrip())
            positions.append(block.position() + start_of_line)

        return positions

    def prev_pydef(self, num: int = 1, num_str: str = "") -> MotionInfo:
        """Return position of previous Python definition."""
        positions = self._get_python_definition_positions()
        cursor = self.get_cursor()
        cur_line_start = cursor.block().position()
        prev_positions = [p for p in positions if p < cur_line_start]
        if not prev_positions:
            return self._set_motion_info(None)
        idx = max(0, len(prev_positions) - num)
        return self._set_motion_info(prev_positions[idx], motion_type=MotionType.LineWise)

    def next_pydef(self, num: int = 1, num_str: str = "") -> MotionInfo:
        """Return position of next Python definition."""
        positions = self._get_python_definition_positions()
        cursor = self.get_cursor()
        cur_line_start = cursor.block().position()
        next_positions = [p for p in positions if p > cur_line_start]
        if not next_positions:
            return self._set_motion_info(None)
        idx = min(len(next_positions) - 1, num - 1)
        return self._set_motion_info(next_positions[idx], motion_type=MotionType.LineWise)

    # ------------------------------------------------------------------
    # Python block navigation helpers
    # ------------------------------------------------------------------
    def _get_python_block_positions(self) -> list[int]:
        """Return start positions of Python code blocks."""
        editor = self.get_editor()
        doc = editor.document()
        positions: list[int] = []

        block_keywords = (
            "def ",
            "async def ",
            "class ",
            "if ",
            "for ",
            "async for ",
            "while ",
            "try:",
            "with ",
            "async with ",
        )

        for line_no, text in enumerate(editor.toPlainText().splitlines()):
            stripped = text.lstrip()
            if any(stripped.startswith(kw) for kw in block_keywords):
                block = doc.findBlockByNumber(line_no)
                if not block.isValid():
                    continue
                start_of_line = len(text) - len(stripped)
                positions.append(block.position() + start_of_line)

        return positions

    def prev_pyblock(self, num: int = 1, num_str: str = "") -> MotionInfo:
        """Return position of previous Python block."""
        positions = self._get_python_block_positions()
        cursor = self.get_cursor()
        cur_line_start = cursor.block().position()
        prev_positions = [p for p in positions if p < cur_line_start]
        if not prev_positions:
            return self._set_motion_info(None)
        idx = max(0, len(prev_positions) - num)
        return self._set_motion_info(prev_positions[idx], motion_type=MotionType.LineWise)

    def next_pyblock(self, num: int = 1, num_str: str = "") -> MotionInfo:
        """Return position of next Python block."""
        positions = self._get_python_block_positions()
        cursor = self.get_cursor()
        cur_line_start = cursor.block().position()
        next_positions = [p for p in positions if p > cur_line_start]
        if not next_positions:
            return self._set_motion_info(None)
        idx = min(len(next_positions) - 1, num - 1)
        return self._set_motion_info(next_positions[idx], motion_type=MotionType.LineWise)
