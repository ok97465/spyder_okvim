# -*- coding: utf-8 -*-
"""Module for motion of vim."""
# %% Import
# Standard library imports
import re
from bisect import bisect_left, bisect_right

# Third party imports
from qtpy.QtWidgets import QTextEdit
from qtpy.QtGui import QTextCursor, QTextDocument
from qtpy.QtCore import QPoint, QRegularExpression
from spyder.config.manager import CONF

# Local imports
from spyder_okvim.utils.misc import BRACKET_PAIR
from spyder_okvim.spyder.config import CONF_SECTION


WHITE_SPACE = ' \t'


class MotionType:
    """Constant for motion type."""

    BlockWise = 0
    LineWise = 1
    CharWise = 2
    CharWiseIncludingEnd = 3


class MotionInfo:
    """Motion Info."""

    def __init__(self):
        self.cursor_pos = None
        self.sel_start = None
        self.sel_end = None
        self.motion_type = MotionType.LineWise


class HelperMotion:
    """Helper for vim motion."""

    def __init__(self, vim_status):
        self.vim_status = vim_status
        self.get_editor = vim_status.get_editor
        self.get_cursor = vim_status.get_cursor
        self.set_cursor = vim_status.set_cursor
        self.set_cursor_pos = vim_status.cursor.set_cursor_pos
        self.motion_info = MotionInfo()

        self.find_cmd_map = {'f': self.find_ch,
                             'F': self.rfind_ch,
                             't': self.t,
                             'T': self.T}

    def _set_motion_info(self, cur_pos, sel_start=None, sel_end=None,
                         motion_type=MotionType.LineWise):
        """Set motion info.

        Parameters
        ----------
        cur_pos: int, optional
            the position of cursor.
        sel_start: int, optional
            the start position of selection.
        sel_end: int, optional
            the end position of selection.
        motion_type: int
            motion type

        Returns
        -------
        MotionInfo
            motion info

        """
        self.motion_info.cursor_pos = cur_pos
        self.motion_info.sel_start = sel_start
        self.motion_info.sel_end = sel_end
        self.motion_info.motion_type = motion_type

        return self.motion_info

    def _get_ch(self, pos):
        """Get character of position."""
        if pos >= self.vim_status.cursor.get_end_position():
            return ''
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

    def zero(self, num=1, num_str=''):
        """Get the start position of the current line.

        Returns
        -------
        MotionInfo
            motion info

        """
        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.StartOfLine)
        return self._set_motion_info(cursor.position(),
                                     motion_type=MotionType.CharWise)

    def l(self, num=1, num_str=''):
        """Get the position on the right side of the cursor.

        Returns
        -------
        MotionInfo
            motion info

        """
        cursor = self.get_cursor()
        pos_cur = cursor.position()

        if cursor.atBlockStart() and cursor.atBlockEnd():
            return self._set_motion_info(pos_cur,
                                         motion_type=MotionType.CharWise)

        cursor.movePosition(QTextCursor.EndOfBlock)
        pos_end = cursor.position()

        pos_new = pos_cur + num
        if pos_new > pos_end:
            pos_new = pos_end

        return self._set_motion_info(pos_new,
                                     motion_type=MotionType.CharWise)

    def h(self, num=1, num_str=''):
        """Get the position on the left side of the cursor.

        Returns
        -------
        MotionInfo
            motion info

        """
        cursor = self.get_cursor()
        pos_cur = cursor.position()

        if cursor.atBlockStart() and cursor.atBlockEnd():
            return self._set_motion_info(pos_cur,
                                         motion_type=MotionType.CharWise)

        cursor.movePosition(QTextCursor.StartOfBlock)
        pos_start = cursor.position()

        pos_new = pos_cur - num
        if pos_new < pos_start:
            pos_new = pos_start

        return self._set_motion_info(pos_new,
                                     motion_type=MotionType.CharWise)

    def k(self, num=1, num_str=''):
        """Get the position above the cursor.

        Returns
        -------
        MotionInfo
            motion info

        """
        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.Up, n=num)
        pos_new = cursor.position()
        if cursor.atBlockEnd() and not cursor.atBlockStart():
            pos_new -= 1

        return self._set_motion_info(pos_new)

    def j(self, num=1, num_str=''):
        """Get the position below the cursor.

        Returns
        -------
        MotionInfo
            motion info

        """
        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.Down, n=num)
        pos_new = cursor.position()
        if cursor.atBlockEnd() and not cursor.atBlockStart():
            pos_new -= 1

        return self._set_motion_info(pos_new)

    def H(self, num=1, num_str=''):
        """Get the position of the top of page."""
        editor = self.get_editor()
        pos = editor.cursorForPosition(QPoint(0, 0)).position()
        return self._set_motion_info(pos)

    def M(self, num=1, num_str=''):
        """Get the position of the middle of page."""
        editor = self.get_editor()
        qpos_mid = int(editor.viewport().height() * 0.5)
        block = editor.cursorForPosition(QPoint(0, qpos_mid)).block()
        return self._set_motion_info(block.position())

    def L(self, num=1, num_str=''):
        """Get the position of the bottom of page."""
        editor = self.get_editor()
        qpos_mid = int(editor.viewport().height())
        block = editor.cursorForPosition(QPoint(0, qpos_mid)).block()
        return self._set_motion_info(block.position())

    def dollar(self, num=1, num_str=''):
        """Get the position of the end of the current line.

        Returns
        -------
        MotionInfo
            motion info

        """
        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.EndOfLine, n=num)
        pos_new = cursor.position()

        return self._set_motion_info(pos_new,
                                     motion_type=MotionType.CharWise)

    def caret(self, num=1, num_str=''):
        """Get the position of the first non-blank character of the line.

        Returns
        -------
        MotionInfo
            motion info

        """
        cursor = self.get_cursor()
        block = cursor.block()
        text = block.text()
        pos = cursor.position()
        if text.strip():
            start_of_line = len(text) - len(text.lstrip())
            pos = block.position() + start_of_line

        return self._set_motion_info(pos,
                                     motion_type=MotionType.CharWise)

    def w(self, num=1, num_str=''):
        """Get the position of the next word.

        Returns
        -------
        MotionInfo
            motion info

        """
        cursor = self.get_cursor()
        for _ in range(num):
            cursor.movePosition(QTextCursor.NextWord)
            if cursor.atBlockEnd():
                cursor.movePosition(QTextCursor.NextWord)
                if self._get_ch(cursor.position()) in WHITE_SPACE:
                    cursor.movePosition(QTextCursor.NextWord)

        return self._set_motion_info(cursor.position(),
                                     motion_type=MotionType.CharWise)

    def w_for_d(self, num=1, num_str=''):
        """Get the position of the next word in d command.

        Returns
        -------
        MotionInfo
            motion info

        """
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

        return self._set_motion_info(cursor.position(),
                                     motion_type=MotionType.CharWise)

    def w_for_c(self, num=1, num_str=''):
        """Get the position of the next word for c command.

        Returns
        -------
        MotionInfo
            motion info

        """
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

        return self._set_motion_info(cursor.position(),
                                     motion_type=MotionType.CharWise)

    def W(self, num=1, num_str=''):
        """Get the position of the next WORD.

        Returns
        -------
        MotionInfo
            motion info

        """
        cursor = self.get_cursor()
        for _ in range(num):
            if cursor.atBlockEnd():
                cursor.movePosition(QTextCursor.NextWord)
                if self._get_ch(cursor.position()) in WHITE_SPACE:
                    cursor.movePosition(QTextCursor.NextWord)
            else:
                cursor.movePosition(QTextCursor.NextWord)
                while (self._get_leading_ch(cursor.position())
                       not in WHITE_SPACE):
                    if cursor.atBlockEnd():
                        cursor.movePosition(QTextCursor.NextWord)
                        if self._get_ch(cursor.position()) in WHITE_SPACE:
                            cursor.movePosition(QTextCursor.NextWord)
                        break
                    cursor.movePosition(QTextCursor.NextWord)

        return self._set_motion_info(cursor.position(),
                                     motion_type=MotionType.CharWise)

    def W_for_d(self, num=1, num_str=''):
        """Get the position of the next WORD.

        Returns
        -------
        MotionInfo
            motion info

        """
        cursor = self.get_cursor()
        for _ in range(num):
            if cursor.atBlockEnd():
                cursor.movePosition(QTextCursor.NextWord)
                if self._get_ch(cursor.position()) in WHITE_SPACE:
                    cursor.movePosition(QTextCursor.NextWord)

            cursor.movePosition(QTextCursor.NextWord)
            while (self._get_leading_ch(cursor.position()) not in WHITE_SPACE):
                if cursor.atBlockEnd():
                    break
                cursor.movePosition(QTextCursor.NextWord)

        return self._set_motion_info(cursor.position(),
                                     motion_type=MotionType.CharWise)

    def W_for_c(self, num=1, num_str=''):
        """Get the position of the next WORD for c command.

        Returns
        -------
        MotionInfo
            motion info

        """
        cursor = self.get_cursor()
        for _ in range(num - 1):
            if cursor.atBlockEnd():
                cursor.movePosition(QTextCursor.NextWord)
                if self._get_ch(cursor.position()) in WHITE_SPACE:
                    cursor.movePosition(QTextCursor.NextWord)
            else:
                cursor.movePosition(QTextCursor.NextWord)
                while (self._get_leading_ch(cursor.position())
                       not in WHITE_SPACE):
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
            while (self._get_ch(cursor.position()) not in WHITE_SPACE
                   and not cursor.atBlockEnd()):
                cursor.movePosition(QTextCursor.Right)
                cursor.movePosition(QTextCursor.EndOfWord)

        return self._set_motion_info(cursor.position(),
                                     motion_type=MotionType.CharWise)

    def b(self, num=1, num_str=''):
        """Get the position of the previous word.

        Returns
        -------
        MotionInfo
            motion info

        """
        cursor = self.get_cursor()

        def move2previousword(_cursor):
            _cursor.movePosition(QTextCursor.PreviousWord)
            while (cursor.atBlockStart()
                    and self._get_ch(cursor.position()) in WHITE_SPACE):
                if _cursor.position() == 0:
                    break
                if _cursor.atBlockStart() and cursor.atBlockEnd():
                    break
                _cursor.movePosition(QTextCursor.PreviousWord)
            return _cursor

        for _ in range(num):
            cursor = move2previousword(cursor)
            while(cursor.atBlockEnd() and not cursor.atBlockStart()):
                cursor = move2previousword(cursor)

        return self._set_motion_info(cursor.position(),
                                     motion_type=MotionType.CharWise)

    def B(self, num=1, num_str=''):
        """Get the position of the previous WORD.

        Returns
        -------
        MotionInfo
            motion info

        """
        cursor = self.get_cursor()

        def move2previousWORD(_cursor):
            _cursor.movePosition(QTextCursor.PreviousWord)
            while(self._get_leading_ch(cursor.position())
                    not in WHITE_SPACE):
                if _cursor.position() == 0:
                    break
                if _cursor.atBlockStart() and cursor.atBlockEnd():
                    break
                _cursor.movePosition(QTextCursor.PreviousWord)
            return _cursor

        for _ in range(num):
            cursor = move2previousWORD(cursor)
            while(cursor.atBlockEnd() and not cursor.atBlockStart()):
                cursor = move2previousWORD(cursor)

        return self._set_motion_info(cursor.position(),
                                     motion_type=MotionType.CharWise)

    def e(self, num=1, num_str=''):
        """Get the position of the end of word.

        Does not stop in an empty line.

        Returns
        -------
        MotionInfo
            motion info

        """
        cursor = self.get_cursor()
        pos_old = cursor.position()

        if not cursor.atBlockEnd():
            cursor.movePosition(QTextCursor.Right)

        def _helper_e(cursor):
            while (cursor.atBlockEnd()
                    or not cursor.block().text().strip()
                    or self._get_ch(cursor.position()) in WHITE_SPACE):
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
                cursor.position(), motion_type=MotionType.CharWiseIncludingEnd)

    def G(self, num=1, num_str=''):
        """Get the position of the Line.

        if num_str is False, this function return the last line position.

        Returns
        -------
        MotionInfo
            motion info

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

    def percent(self, num=1, num_str=''):
        """Get the position of matching bracket."""
        txt = self.get_editor().toPlainText()
        cursor_pos = self.get_cursor().position()
        pos_start = None
        pos_end = None

        for match in re.finditer(r'[\(\[\{\}\]\)]', txt[cursor_pos::]):
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
            pos_end, motion_type=MotionType.CharWiseIncludingEnd)

    def find_ch(self, ch, num=1, by_repeat_cmd=False):
        """Get the position of the next occurrence of a character."""
        if by_repeat_cmd is False:
            self.vim_status.find_info.set('f', ch)
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
            return self._set_motion_info(None,
                                         motion_type=MotionType.CharWise)
        else:
            return self._set_motion_info(
                ch_pos + block.position(),
                motion_type=MotionType.CharWiseIncludingEnd)

    def rfind_ch(self, ch, num=1, by_repeat_cmd=False):
        """Get the position of the previous occurrence of a character."""
        if by_repeat_cmd is False:
            self.vim_status.find_info.set('F', ch)
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
            return self._set_motion_info(None,
                                         motion_type=MotionType.CharWise)
        else:
            return self._set_motion_info(ch_pos + block.position(),
                                         motion_type=MotionType.CharWise)

    def t(self, ch, num=1, by_repeat_cmd=False):
        """Get the position - 1 of the next occurrence of a character."""
        if by_repeat_cmd is False:
            self.vim_status.find_info.set('t', ch)
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
            return self._set_motion_info(None,
                                         motion_type=MotionType.CharWise)
        else:
            return self._set_motion_info(
                ch_pos + block.position(),
                motion_type=MotionType.CharWiseIncludingEnd)

    def T(self, ch, num=1, by_repeat_cmd=False):
        """Get the position + 1 of the previous occurrence of a character."""
        if by_repeat_cmd is False:
            self.vim_status.find_info.set('T', ch)
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
            return self._set_motion_info(None,
                                         motion_type=MotionType.CharWise)

        ch_pos += 1
        if ch_pos >= block.length():
            return self._set_motion_info(None,
                                         motion_type=MotionType.CharWise)
        return self._set_motion_info(ch_pos + block.position(),
                                     motion_type=MotionType.CharWise)

    def semicolon(self, num=1, num_str=''):
        """Repeat latest f, t, F or T."""
        name = self.vim_status.find_info.cmd_name
        ch = self.vim_status.find_info.ch
        method = self.find_cmd_map.get(name, None)
        if method is None:
            return self._set_motion_info(None,
                                         motion_type=MotionType.CharWise)
        motion_info = method(ch, num, True)
        return motion_info

    def comma(self, num=1, num_str=''):
        """Repeat latest f, t, F or T in opposite direction."""
        name = self.vim_status.find_info.cmd_name
        ch = self.vim_status.find_info.ch
        method = self.find_cmd_map.get(name.swapcase(), None)
        if method is None:
            return self._set_motion_info(None,
                                         motion_type=MotionType.CharWise)
        motion_info = method(ch, num, True)
        return motion_info

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
            quote_pos = [m.start() for m in re.finditer(quote,
                                                        text[:cursor_pos])]
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

        return self._set_motion_info(None, sel_start, sel_end,
                                     motion_type=MotionType.BlockWise)

    def _include_trailing_white(self, pos_end):
        """Add the position of trailing white space."""
        cursor = self.get_cursor()

        cursor.setPosition(pos_end)

        # including trailing text
        if (pos_end < self.vim_status.cursor.get_end_position()
                and not cursor.atBlockEnd()):
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
        text = text[:pos_start - block.position()]

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
            quote_pos = [m.start() for m in re.finditer(quote,
                                                        text[:cursor_pos])]
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

        return self._set_motion_info(None, sel_start, sel_end,
                                     motion_type=MotionType.BlockWise)

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

        return self._set_motion_info(None, sel_start, sel_end,
                                     motion_type=MotionType.BlockWise)

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

            while (not cursor.atBlockStart()
                    and self._get_leading_ch(cursor.position()) not in
                    WHITE_SPACE):
                cursor.movePosition(QTextCursor.Left)
                cursor.movePosition(QTextCursor.StartOfWord)

            sel_start = cursor.position()

        for idx in range(num):
            if idx % 2 == 0:
                if cursor.atBlockEnd():
                    cursor.movePosition(QTextCursor.NextWord, n=2)
                else:
                    cursor.movePosition(QTextCursor.EndOfWord)
                    while (not cursor.atBlockEnd()
                           and self._get_ch(cursor.position())
                           not in WHITE_SPACE):
                        cursor.movePosition(QTextCursor.Right)
                        if (self._get_ch(cursor.position())
                                not in WHITE_SPACE):
                            cursor.movePosition(QTextCursor.EndOfWord)
            else:
                # go to the end of blank
                if cursor.atBlockEnd():
                    cursor.movePosition(QTextCursor.NextWord, n=2)
                else:
                    cursor.movePosition(QTextCursor.NextWord)

        sel_end = cursor.position()

        return self._set_motion_info(None, sel_start, sel_end,
                                     motion_type=MotionType.BlockWise)

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

        return self._set_motion_info(None, sel_start, sel_end,
                                     motion_type=MotionType.BlockWise)

    def a_bracket(self, num, bracket):
        """Get the position of the bracket block."""
        # Todo: apply num
        pair_bracket = {'(': ['(', ')', r'[()]'],
                        ')': ['(', ')', r'[()]'],
                        '[': ['[', ']', r'[\[\]]'],
                        ']': ['[', ']', r'[\[\]]'],
                        '{': ['{', '}', r'[{}]'],
                        '}': ['{', '}', r'[{}]']}
        b_open, b_close, pattern_str = pair_bracket[bracket]
        txt = self.get_editor().toPlainText()

        sel_start = None
        sel_end = None
        cursor = self.get_cursor()
        cursor_pos = cursor.position()

        pattern = re.compile(pattern_str)

        # Find position of close bracket
        if self._get_ch(cursor_pos) == b_close:
            sel_end = cursor_pos + 1
        else:
            n_open = 0
            for match in pattern.finditer(txt[cursor_pos + 1::]):
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

        return self._set_motion_info(None, sel_start, sel_end,
                                     motion_type=MotionType.BlockWise)

    def i_bracket(self, num, bracket):
        """Get the position of the bracket inner block."""
        motion_info = self.a_bracket(num, bracket)
        if (motion_info.sel_start is not None
                and motion_info.sel_end is not None):
            motion_info.sel_start += 1
            motion_info.sel_end -= 1
            if motion_info.sel_start == motion_info.sel_end:
                motion_info.sel_start = None
                motion_info.sel_end = None

        return motion_info

    def search(self, txt):
        """Search regular expressions key inside document(from spyder_vim)."""
        editor = self.get_editor()
        cursor = QTextCursor(editor.document())
        cursor.movePosition(QTextCursor.Start)

        # Apply the option for search
        is_ignorecase = CONF.get(CONF_SECTION, 'ignorecase')
        is_smartcase = CONF.get(CONF_SECTION, 'smartcase')

        if is_ignorecase is True:
            option = None
            self.vim_status.search.ignorecase = True

            if is_smartcase and txt.lower() != txt:
                option = QTextDocument.FindCaseSensitively
                self.vim_status.search.ignorecase = False
        else:
            option = QTextDocument.FindCaseSensitively
            self.vim_status.search.ignorecase = False

        # Find key in document forward
        search_stack = []
        if option:
            cursor = editor.document().find(QRegularExpression(txt),
                                            options=option)
        else:
            cursor = editor.document().find(QRegularExpression(txt))

        back = self.vim_status.search.color_bg
        fore = self.vim_status.search.color_fg
        while not cursor.isNull():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(back)
            selection.format.setForeground(fore)
            selection.cursor = cursor
            search_stack.append(selection)
            if option:
                cursor = editor.document().find(
                        QRegularExpression(txt), cursor, options=option)
            else:
                cursor = editor.document().find(
                        QRegularExpression(txt), cursor)
        self.vim_status.cursor.set_extra_selections(
            'vim_search', [i for i in search_stack])
        editor.update_extra_selections()

        self.vim_status.search.selection_list = search_stack
        self.vim_status.search.txt_searched = txt

    def n(self, num=1, num_str=''):
        """Get position to the next searched text(from spyder-vim)."""
        pos_list = self.vim_status.search.get_sel_start_list()
        if not pos_list:
            return self._set_motion_info(None)

        txt = self.vim_status.search.txt_searched
        self.vim_status.set_message(f'/{txt}')

        cursor_pos = self.get_cursor().position()

        idx = bisect_right(pos_list, cursor_pos)
        if idx == len(pos_list):
            idx = 0

        idx += num - 1
        idx = idx % len(pos_list)

        return self._set_motion_info(pos_list[idx],
                                     motion_type=MotionType.CharWise)

    def N(self, num=1, num_str=''):
        """Get position to the previous searched text(from spyder-vim)."""
        pos_list = self.vim_status.search.get_sel_start_list()
        n_pos_list = len(pos_list)
        if not pos_list:
            return self._set_motion_info(None)

        txt = self.vim_status.search.txt_searched
        self.vim_status.set_message(f'?{txt}')

        cursor_pos = self.get_cursor().position()

        idx = bisect_left(pos_list, cursor_pos)
        idx -= num - 1
        idx = idx % n_pos_list

        return self._set_motion_info(pos_list[idx - 1],
                                     motion_type=MotionType.CharWise)

    def space(self, num=1, num_str=''):
        """Get the position on the right side of the cursor.

        Returns
        -------
        MotionInfo
            motion info

        """
        cursor = self.get_cursor()

        for _ in range(num):
            cursor.movePosition(QTextCursor.Right)
            if cursor.atBlockEnd():
                cursor.movePosition(QTextCursor.Right)

        return self._set_motion_info(cursor.position(),
                                     motion_type=MotionType.CharWise)

    def backspace(self, num=1, num_str=''):
        """Get the position on the right side of the cursor.

        Returns
        -------
        MotionInfo
            motion info

        """
        cursor = self.get_cursor()

        cursor.movePosition(QTextCursor.Left, n=num)

        return self._set_motion_info(cursor.position(),
                                     motion_type=MotionType.CharWise)

    def enter(self, num=1, num_str=''):
        """Get the position below the cursor.

        Returns
        -------
        MotionInfo
            motion info

        """
        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.Down, n=num)
        block = cursor.block()
        text = block.text()
        pos = cursor.position()

        if text.strip():
            start_of_line = len(text) - len(text.lstrip())
            pos = block.position() + start_of_line

        return self._set_motion_info(pos)

