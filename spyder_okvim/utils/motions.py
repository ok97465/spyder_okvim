# -*- coding: utf-8 -*-
"""Compute cursor, word and structural motions for Vim commands.

Text-object ranges are composed through TextObjects; stateful search and Leap
remain owned by their existing collaborators. Computed positions use Qt UTF-16
coordinates and are applied by the command's mode-specific cursor policy.
"""

# Standard Libraries
import re
from bisect import bisect_left, bisect_right
from typing import TYPE_CHECKING

# Third Party Libraries
from qtpy.QtCore import QPoint
from qtpy.QtGui import QTextCursor

# Project Libraries
from spyder_okvim.utils.leap_helpers import LeapHelper
from spyder_okvim.utils.motion import MotionInfo, MotionType
from spyder_okvim.utils.search_helpers import resolve_ignorecase
from spyder_okvim.utils.text_constants import BRACKET_PAIR
from spyder_okvim.utils.text_objects import TextObjects

if TYPE_CHECKING:  # pragma: no cover - typing helpers
    # Project Libraries
    from spyder_okvim.utils.cell_helpers import CellRegion

WHITE_SPACE = " \t"


class CursorMotions:
    """Compute motions while retaining only this executor's Leap/find context.

    Vim key names are kept for direct command dispatch. These operations return
    MotionInfo rather than editing text; search/mark/Leap methods additionally
    update their documented sessions or display through the supplied Vim state.
    """

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

        self.text_objects = TextObjects(self.get_cursor)
        self.leap_helper = LeapHelper(vim_status, MotionInfo)

        self.find_cmd_map = {
            "f": self.find_ch,
            "F": self.rfind_ch,
            "t": self.t,
            "T": self.T,
            "l": self.leap_helper.leap,
            "L": self.leap_helper.reverse_leap,
            "s": self.leap_helper.leap,
            "S": self.leap_helper.reverse_leap,
            "z": self.leap_helper.leap,
            "Z": self.leap_helper.reverse_leap,
        }

    # ------------------------------------------------------------------
    # Cell navigation helpers
    # ------------------------------------------------------------------
    def _locate_cell_index(
        self, cells: list["CellRegion"], cursor_pos: int
    ) -> int | None:
        """Return the index of the cell containing ``cursor_pos``."""
        if not cells:
            return None

        for idx, cell in enumerate(cells):
            if cell.start_position <= cursor_pos < cell.end_position:
                return idx

        if cursor_pos < cells[0].start_position:
            return 0

        for idx in range(len(cells) - 1, -1, -1):
            if cursor_pos >= cells[idx].start_position:
                return idx

        return None

    def prev_cell(self, count: int = 1, count_text: str = "") -> MotionInfo:
        """Return motion info for the previous code cell."""
        cells = self.vim_status.get_cells()
        if len(cells) <= 1:
            return MotionInfo(None)

        cursor = self.get_cursor()
        cursor_pos = cursor.position()
        current_idx = self._locate_cell_index(cells, cursor_pos)
        if current_idx is None:
            return MotionInfo(None)

        target_idx = current_idx - count
        if target_idx < 0:
            return MotionInfo(None)

        target_cell = cells[target_idx]
        target_pos = target_cell.start_position

        current_cell = cells[current_idx]
        current_header_block = cursor.document().findBlock(current_cell.start_position)
        sel_end_block = current_header_block.previous()
        if sel_end_block.isValid():
            sel_end = sel_end_block.position() + sel_end_block.length() - 1
        else:
            sel_end = target_pos

        return MotionInfo(
            target_pos,
            sel_start=target_pos,
            sel_end=sel_end,
            motion_type=MotionType.LineWise,
        )

    def next_cell(self, count: int = 1, count_text: str = "") -> MotionInfo:
        """Return motion info for the next code cell."""
        cells = self.vim_status.get_cells()
        if len(cells) <= 1:
            return MotionInfo(None)

        cursor = self.get_cursor()
        cursor_pos = cursor.position()
        current_idx = self._locate_cell_index(cells, cursor_pos)
        if current_idx is None:
            return MotionInfo(None)

        target_idx = current_idx + count
        if target_idx >= len(cells):
            return MotionInfo(None)

        target_cell = cells[target_idx]
        target_pos = target_cell.start_position

        target_block = cursor.document().findBlock(target_pos)
        prev_block = target_block.previous()
        if prev_block.isValid():
            sel_end = prev_block.position() + prev_block.length() - 1
        else:
            sel_end = target_block.position()

        sel_start_block = cursor.block()
        sel_start = sel_start_block.position()

        if sel_end < sel_start:
            sel_end = sel_start

        return MotionInfo(
            target_pos,
            sel_start=sel_start,
            sel_end=sel_end,
            motion_type=MotionType.LineWise,
        )

    def i_cell(self, count: int = 1) -> MotionInfo:
        """Return motion info covering the current cell and subsequent cells."""
        cells = self.vim_status.get_cells()
        if not cells:
            return MotionInfo(None)

        cursor = self.get_cursor()
        cursor_pos = cursor.position()
        current_idx = self._locate_cell_index(cells, cursor_pos)
        if current_idx is None:
            return MotionInfo(None)

        count = max(1, count)
        end_idx = min(len(cells) - 1, current_idx + count - 1)

        document = cursor.document()
        start_cell = cells[current_idx]
        start_block = document.findBlockByNumber(start_cell.start_line)
        if not start_block.isValid():
            start_block = document.firstBlock()
        sel_start = start_block.position()

        end_cell = cells[end_idx]
        end_block = document.findBlockByNumber(end_cell.end_line)
        if not end_block.isValid():
            end_block = document.lastBlock()
        sel_end = end_block.position() + end_block.length() - 1
        if sel_end < sel_start:
            sel_end = sel_start

        return MotionInfo(
            sel_start,
            sel_start=sel_start,
            sel_end=sel_end,
            motion_type=MotionType.LineWise,
        )

    def _character_at(self, position):
        """Return the Qt character at a UTF-16 position, or empty at the end."""
        if position >= self.vim_status.cursor.get_end_position():
            return ""
        cursor = self.get_cursor()
        cursor.setPosition(position)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
        return cursor.selectedText()

    def _character_before(self, position):
        """Return the Qt character preceding a UTF-16 position."""
        cursor = self.get_cursor()
        cursor.setPosition(position)
        cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor)
        return cursor.selectedText()

    def zero(self, count=1, count_text=""):
        """Get the start position of the current line."""
        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.StartOfLine)
        return MotionInfo(cursor.position(), motion_type=MotionType.CharWise)

    def l(self, count=1, count_text=""):
        """Get the position on the right side of the cursor."""
        cursor = self.get_cursor()
        pos_cur = cursor.position()

        if cursor.atBlockStart() and cursor.atBlockEnd():
            return MotionInfo(pos_cur, motion_type=MotionType.CharWise)

        cursor.movePosition(QTextCursor.EndOfBlock)
        pos_end = cursor.position()

        pos_new = pos_cur + count
        if pos_new > pos_end:
            pos_new = pos_end

        return MotionInfo(pos_new, motion_type=MotionType.CharWise)

    def h(self, count=1, count_text=""):
        """Get the position on the left side of the cursor."""
        cursor = self.get_cursor()
        pos_cur = cursor.position()

        if cursor.atBlockStart() and cursor.atBlockEnd():
            return MotionInfo(pos_cur, motion_type=MotionType.CharWise)

        cursor.movePosition(QTextCursor.StartOfBlock)
        pos_start = cursor.position()

        pos_new = pos_cur - count
        if pos_new < pos_start:
            pos_new = pos_start

        return MotionInfo(pos_new, motion_type=MotionType.CharWise)

    def k(self, count=1, count_text=""):
        """Get the position above the cursor."""
        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.Up, n=count)
        pos_new = cursor.position()
        if cursor.atBlockEnd() and not cursor.atBlockStart():
            pos_new -= 1

        return MotionInfo(pos_new)

    def j(self, count=1, count_text=""):
        """Get the position below the cursor."""
        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.Down, n=count)
        pos_new = cursor.position()
        if cursor.atBlockEnd() and not cursor.atBlockStart():
            pos_new -= 1

        return MotionInfo(pos_new)

    def H(self, count=1, count_text=""):
        """Get the position of the top of page."""
        editor = self.get_editor()
        pos = editor.cursorForPosition(QPoint(0, 0)).position()
        return MotionInfo(pos)

    def M(self, count=1, count_text=""):
        """Get the position of the middle of page."""
        editor = self.get_editor()
        qpos_mid = int(editor.viewport().height() * 0.5)
        block = editor.cursorForPosition(QPoint(0, qpos_mid)).block()
        return MotionInfo(block.position())

    def L(self, count=1, count_text=""):
        """Get the position of the bottom of page."""
        editor = self.get_editor()
        qpos_mid = int(editor.viewport().height())
        block = editor.cursorForPosition(QPoint(0, qpos_mid)).block()
        return MotionInfo(block.position())

    def dollar(self, count=1, count_text=""):
        """Get the position of the end of the current line."""
        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.EndOfLine, n=count)
        pos_new = cursor.position()

        return MotionInfo(pos_new, motion_type=MotionType.CharWise)

    def caret(self, count=1, count_text=""):
        """Get the position of the first non-blank character of the line."""
        cursor = self.get_cursor()
        block = cursor.block()
        text = block.text()
        pos = cursor.position()
        if text.strip():
            start_of_line = len(text) - len(text.lstrip())
            pos = block.position() + start_of_line

        return MotionInfo(pos, motion_type=MotionType.CharWise)

    def w(self, count=1, count_text=""):
        """Get the position of the next word."""
        cursor = self.get_cursor()
        for _ in range(count):
            cursor.movePosition(QTextCursor.NextWord)
            if cursor.atBlockEnd():
                cursor.movePosition(QTextCursor.NextWord)
                if self._character_at(cursor.position()) in WHITE_SPACE:
                    cursor.movePosition(QTextCursor.NextWord)

        return MotionInfo(cursor.position(), motion_type=MotionType.CharWise)

    def w_for_d(self, count=1, count_text=""):
        """Get the position of the next word in d command."""
        cursor = self.get_cursor()
        for _ in range(count):
            if cursor.atBlockEnd():
                cursor.movePosition(QTextCursor.NextWord)
                if self._character_at(cursor.position()) in WHITE_SPACE:
                    cursor.movePosition(QTextCursor.NextWord, n=2)
                else:
                    cursor.movePosition(QTextCursor.NextWord)
            else:
                cursor.movePosition(QTextCursor.NextWord)

        return MotionInfo(cursor.position(), motion_type=MotionType.CharWise)

    def w_for_c(self, count=1, count_text=""):
        """Get the position of the next word for c command."""
        cursor = self.get_cursor()
        for _ in range(count - 1):
            cursor.movePosition(QTextCursor.NextWord)
            if cursor.atBlockEnd():
                cursor.movePosition(QTextCursor.NextWord)
                if self._character_at(cursor.position()) in WHITE_SPACE:
                    cursor.movePosition(QTextCursor.NextWord)

        if self._character_at(cursor.position()) in WHITE_SPACE:
            cursor.movePosition(QTextCursor.NextWord)
        else:
            cursor.movePosition(QTextCursor.EndOfWord)

        return MotionInfo(cursor.position(), motion_type=MotionType.CharWise)

    def W(self, count=1, count_text=""):
        """Get the position of the next WORD."""
        cursor = self.get_cursor()
        for _ in range(count):
            if cursor.atBlockEnd():
                cursor.movePosition(QTextCursor.NextWord)
                if self._character_at(cursor.position()) in WHITE_SPACE:
                    cursor.movePosition(QTextCursor.NextWord)
            else:
                cursor.movePosition(QTextCursor.NextWord)
                while self._character_before(cursor.position()) not in WHITE_SPACE:
                    if cursor.atBlockEnd():
                        cursor.movePosition(QTextCursor.NextWord)
                        if self._character_at(cursor.position()) in WHITE_SPACE:
                            cursor.movePosition(QTextCursor.NextWord)
                        break
                    cursor.movePosition(QTextCursor.NextWord)

        return MotionInfo(cursor.position(), motion_type=MotionType.CharWise)

    def W_for_d(self, count=1, count_text=""):
        """Get the position of the next WORD."""
        cursor = self.get_cursor()
        for _ in range(count):
            if cursor.atBlockEnd():
                cursor.movePosition(QTextCursor.NextWord)
                if self._character_at(cursor.position()) in WHITE_SPACE:
                    cursor.movePosition(QTextCursor.NextWord)

            cursor.movePosition(QTextCursor.NextWord)
            while self._character_before(cursor.position()) not in WHITE_SPACE:
                if cursor.atBlockEnd():
                    break
                cursor.movePosition(QTextCursor.NextWord)

        return MotionInfo(cursor.position(), motion_type=MotionType.CharWise)

    def W_for_c(self, count=1, count_text=""):
        """Get the position of the next WORD for c command."""
        cursor = self.get_cursor()
        for _ in range(count - 1):
            if cursor.atBlockEnd():
                cursor.movePosition(QTextCursor.NextWord)
                if self._character_at(cursor.position()) in WHITE_SPACE:
                    cursor.movePosition(QTextCursor.NextWord)
            else:
                cursor.movePosition(QTextCursor.NextWord)
                while self._character_before(cursor.position()) not in WHITE_SPACE:
                    if cursor.atBlockEnd():
                        cursor.movePosition(QTextCursor.NextWord)
                        if self._character_at(cursor.position()) in WHITE_SPACE:
                            cursor.movePosition(QTextCursor.NextWord)
                        break
                    cursor.movePosition(QTextCursor.NextWord)

        if self._character_at(cursor.position()) in WHITE_SPACE:
            cursor.movePosition(QTextCursor.NextWord)
        else:
            cursor.movePosition(QTextCursor.EndOfWord)
            while (
                self._character_at(cursor.position()) not in WHITE_SPACE
                and not cursor.atBlockEnd()
            ):
                cursor.movePosition(QTextCursor.Right)
                cursor.movePosition(QTextCursor.EndOfWord)

        return MotionInfo(cursor.position(), motion_type=MotionType.CharWise)

    def b(self, count=1, count_text=""):
        """Get the position of the previous word."""
        cursor = self.get_cursor()

        def previous_word(_cursor):
            _cursor.movePosition(QTextCursor.PreviousWord)
            while (
                cursor.atBlockStart()
                and self._character_at(cursor.position()) in WHITE_SPACE
            ):
                if _cursor.position() == 0:
                    break
                if _cursor.atBlockStart() and cursor.atBlockEnd():
                    break
                _cursor.movePosition(QTextCursor.PreviousWord)
            return _cursor

        for _ in range(count):
            cursor = previous_word(cursor)
            while cursor.atBlockEnd() and not cursor.atBlockStart():
                cursor = previous_word(cursor)

        return MotionInfo(cursor.position(), motion_type=MotionType.CharWise)

    def B(self, count=1, count_text=""):
        """Get the position of the previous WORD."""
        cursor = self.get_cursor()

        def previous_WORD(_cursor):
            _cursor.movePosition(QTextCursor.PreviousWord)
            while self._character_before(cursor.position()) not in WHITE_SPACE:
                if _cursor.position() == 0:
                    break
                if _cursor.atBlockStart() and cursor.atBlockEnd():
                    break
                _cursor.movePosition(QTextCursor.PreviousWord)
            return _cursor

        for _ in range(count):
            cursor = previous_WORD(cursor)
            while cursor.atBlockEnd() and not cursor.atBlockStart():
                cursor = previous_WORD(cursor)

        return MotionInfo(cursor.position(), motion_type=MotionType.CharWise)

    def e(self, count=1, count_text=""):
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
                or self._character_at(cursor.position()) in WHITE_SPACE
            ):
                cursor.movePosition(QTextCursor.NextWord)
                if cursor.atEnd():
                    break

            cursor.movePosition(QTextCursor.EndOfWord)
            return cursor

        for _ in range(count):
            cursor = _helper_e(cursor)

        if pos_old < cursor.position():
            cursor.movePosition(QTextCursor.Left)

        return MotionInfo(
            cursor.position(), motion_type=MotionType.CharWiseIncludingEnd
        )

    def G(self, count=1, count_text=""):
        """Get the position of the Line.

        if num_str is False, this function return the last line position.

        """
        editor = self.get_editor()
        n_block = editor.blockCount()

        if count > n_block:
            cursor = self.get_cursor()
            return MotionInfo(cursor.position())

        if count_text:
            block = editor.document().findBlockByNumber(count - 1)
        else:
            block = editor.document().findBlockByNumber(n_block - 1)

        text = block.text()
        start_of_line = len(text) - len(text.lstrip())
        if not text.strip() and text:
            start_of_line -= 1
        pos = block.position() + start_of_line

        return MotionInfo(pos)

    def percent(self, count=1, count_text=""):
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
            return MotionInfo(None)

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

        return MotionInfo(pos_end, motion_type=MotionType.CharWiseIncludingEnd)

    def find_ch(self, ch, count=1, by_repeat_cmd=False):
        """Get the position of the next occurrence of a character."""
        if by_repeat_cmd is False:
            self.vim_status.find_info.set("f", ch)
        cursor = self.get_cursor()
        block = cursor.block()
        search_pos = cursor.positionInBlock() + 1
        txt = block.text()
        ch_pos = -1
        for _ in range(count):
            ch_pos = txt.find(ch, search_pos)
            if ch_pos < 0:
                break
            search_pos = ch_pos + 1

        if ch_pos < 0:
            return MotionInfo(None, motion_type=MotionType.CharWise)
        else:
            return MotionInfo(
                ch_pos + block.position(), motion_type=MotionType.CharWiseIncludingEnd
            )

    def rfind_ch(self, ch, count=1, by_repeat_cmd=False):
        """Get the position of the previous occurrence of a character."""
        if by_repeat_cmd is False:
            self.vim_status.find_info.set("F", ch)
        cursor = self.get_cursor()
        block = cursor.block()
        search_pos = cursor.positionInBlock()
        txt = block.text()
        ch_pos = -1
        for _ in range(count):
            ch_pos = txt[:search_pos].rfind(ch)
            if ch_pos < 0:
                break
            search_pos = ch_pos

        if ch_pos < 0:
            return MotionInfo(None, motion_type=MotionType.CharWise)
        else:
            return MotionInfo(
                ch_pos + block.position(), motion_type=MotionType.CharWise
            )

    def t(self, ch, count=1, by_repeat_cmd=False):
        """Get the position - 1 of the next occurrence of a character."""
        if by_repeat_cmd is False:
            self.vim_status.find_info.set("t", ch)
        cursor = self.get_cursor()
        block = cursor.block()
        search_pos = cursor.positionInBlock() + 1
        txt = block.text()
        ch_pos = -1
        for idx in range(count):
            if count == 1 and by_repeat_cmd is True:
                search_pos += 1
            ch_pos = txt.find(ch, search_pos)
            if ch_pos < 0:
                break
            search_pos = ch_pos + 1

        ch_pos -= 1
        if ch_pos < 0:
            return MotionInfo(None, motion_type=MotionType.CharWise)
        else:
            return MotionInfo(
                ch_pos + block.position(), motion_type=MotionType.CharWiseIncludingEnd
            )

    def T(self, ch, count=1, by_repeat_cmd=False):
        """Get the position + 1 of the previous occurrence of a character."""
        if by_repeat_cmd is False:
            self.vim_status.find_info.set("T", ch)
        cursor = self.get_cursor()
        block = cursor.block()
        search_pos = cursor.positionInBlock()
        txt = block.text()
        ch_pos = -1
        for idx in range(count):
            if count == 1 and by_repeat_cmd is True:
                search_pos -= 1
                if search_pos == -1:
                    break
            ch_pos = txt[:search_pos].rfind(ch)
            if ch_pos < 0:
                break
            search_pos = ch_pos

        if ch_pos < 0:
            return MotionInfo(None, motion_type=MotionType.CharWise)

        ch_pos += 1
        if ch_pos >= block.length():
            return MotionInfo(None, motion_type=MotionType.CharWise)
        return MotionInfo(ch_pos + block.position(), motion_type=MotionType.CharWise)

    def semicolon(self, count=1, count_text=""):
        """Repeat latest f, t, F or T."""
        name = self.vim_status.find_info.cmd_name
        ch = self.vim_status.find_info.ch
        method = self.find_cmd_map.get(name, None)
        if method is None:
            return MotionInfo(None, motion_type=MotionType.CharWise)
        motion_info = method(ch, count, True)
        return motion_info

    def comma(self, count=1, count_text=""):
        """Repeat latest f, t, F or T in opposite direction."""
        name = self.vim_status.find_info.cmd_name
        ch = self.vim_status.find_info.ch
        method = self.find_cmd_map.get(name.swapcase(), None)
        if method is None:
            return MotionInfo(None, motion_type=MotionType.CharWise)
        motion_info = method(ch, count, True)
        return motion_info

    def apostrophe(self, mark: str):
        """Return linewise position of mark."""
        motion = self.backtick(mark)
        if motion.cursor_pos is None:
            return MotionInfo(None)
        block = self.get_editor().document().findBlock(motion.cursor_pos)
        return MotionInfo(block.position(), motion_type=MotionType.LineWise)

    def backtick(self, mark: str):
        """Return charwise position of mark."""
        bookmarks = self.vim_status.bookmark_manager
        info = bookmarks.get_bookmark(mark)
        if not info:
            return MotionInfo(None)
        current = self.vim_status.get_editorstack().get_current_filename()
        if info.get("file") != current:
            return MotionInfo(None)
        editor = self.get_editor()
        block = editor.document().findBlockByNumber(info["line"])
        if not block.isValid():
            if mark.isupper():
                bookmarks.bookmarks_global.pop(mark, None)
                bookmarks.save()
            else:
                bookmarks.bookmarks[current].pop(mark, None)
            return MotionInfo(None)
        pos = block.position() + min(info["col"], block.length() - 1)
        return MotionInfo(pos, motion_type=MotionType.CharWiseIncludingEnd)

    def search(self, text: str, forward: bool = True) -> None:
        """Search in ``forward`` direction, reusing the previous pattern if empty."""
        text = text or self.vim_status.search.txt_searched
        if not text:
            return
        ignorecase = resolve_ignorecase(
            text,
            ignorecase=self.vim_status.settings.ignorecase,
            smartcase=self.vim_status.settings.smartcase,
        )
        self.vim_status.search.search(text, ignorecase=ignorecase, forward=forward)

    def n(self, count: int = 1, count_text: str = "") -> MotionInfo:
        """Move to a match in the direction of the last search."""
        return self._repeat_search(count, self.vim_status.search.forward)

    def N(self, count: int = 1, count_text: str = "") -> MotionInfo:
        """Move to a match opposite the direction of the last search."""
        return self._repeat_search(count, not self.vim_status.search.forward)

    def _repeat_search(self, count: int, forward: bool) -> MotionInfo:
        """Find a counted match while preserving the saved search direction."""
        positions = self.vim_status.search.get_sel_start_list()
        if not positions:
            return MotionInfo(None)
        text = self.vim_status.search.txt_searched
        prefix = "/" if forward else "?"
        self.vim_status.set_message(f"{prefix}{text}")
        cursor_pos = self.get_cursor().position()
        if forward:
            idx = bisect_right(positions, cursor_pos) + count - 1
        else:
            idx = bisect_left(positions, cursor_pos) - count
        idx %= len(positions)
        return MotionInfo(positions[idx], motion_type=MotionType.CharWise)

    def asterisk(self, count: int = 1, count_text: str = "") -> MotionInfo:
        """Search forward for the word under the cursor."""
        word = self.get_editor().get_current_word()
        if word is None:
            return MotionInfo(None)
        self.search(rf"\b{word}\b", forward=True)
        return self.n(count=count)

    def sharp(self, count: int = 1, count_text: str = "") -> MotionInfo:
        """Search backward for the word under the cursor."""
        word = self.get_editor().get_current_word()
        if word is None:
            return MotionInfo(None)
        self.search(rf"\b{word}\b", forward=False)
        return self.n(count=count)

    def space(self, count=1, count_text=""):
        """Get the position on the right side of the cursor."""
        cursor = self.get_cursor()

        for _ in range(count):
            cursor.movePosition(QTextCursor.Right)
            if cursor.atBlockEnd():
                cursor.movePosition(QTextCursor.Right)

        return MotionInfo(cursor.position(), motion_type=MotionType.CharWise)

    def backspace(self, count=1, count_text=""):
        """Return a characterwise motion to the preceding Qt character."""
        cursor = self.get_cursor()

        cursor.movePosition(QTextCursor.Left, n=count)

        return MotionInfo(cursor.position(), motion_type=MotionType.CharWise)

    def enter(self, count=1, count_text=""):
        """Get the position below the cursor."""
        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.Down, n=count)
        block = cursor.block()
        text = block.text()
        pos = cursor.position()

        if text.strip():
            start_of_line = len(text) - len(text.lstrip())
            pos = block.position() + start_of_line

        return MotionInfo(pos)

    # ------------------------------------------------------------------
    # Python navigation helpers
    # ------------------------------------------------------------------

    def prev_pydef(self, count: int = 1, count_text: str = "") -> MotionInfo:
        """Return position of previous Python definition."""
        positions = self.vim_status.host.python_definition_positions()
        cursor = self.get_cursor()
        cur_line_start = cursor.block().position()
        prev_positions = [p for p in positions if p < cur_line_start]
        if not prev_positions:
            return MotionInfo(None)
        idx = max(0, len(prev_positions) - count)
        return MotionInfo(prev_positions[idx], motion_type=MotionType.LineWise)

    def next_pydef(self, count: int = 1, count_text: str = "") -> MotionInfo:
        """Return position of next Python definition."""
        positions = self.vim_status.host.python_definition_positions()
        cursor = self.get_cursor()
        cur_line_start = cursor.block().position()
        next_positions = [p for p in positions if p > cur_line_start]
        if not next_positions:
            return MotionInfo(None)
        idx = min(len(next_positions) - 1, count - 1)
        return MotionInfo(next_positions[idx], motion_type=MotionType.LineWise)

    # ------------------------------------------------------------------
    # Python block navigation helpers
    # ------------------------------------------------------------------

    def prev_pyblock(self, count: int = 1, count_text: str = "") -> MotionInfo:
        """Return position of previous Python block."""
        positions = self.vim_status.host.python_block_positions()
        cursor = self.get_cursor()
        cur_line_start = cursor.block().position()
        prev_positions = [p for p in positions if p < cur_line_start]
        if not prev_positions:
            return MotionInfo(None)
        idx = max(0, len(prev_positions) - count)
        return MotionInfo(prev_positions[idx], motion_type=MotionType.LineWise)

    def next_pyblock(self, count: int = 1, count_text: str = "") -> MotionInfo:
        """Return position of next Python block."""
        positions = self.vim_status.host.python_block_positions()
        cursor = self.get_cursor()
        cur_line_start = cursor.block().position()
        next_positions = [p for p in positions if p > cur_line_start]
        if not next_positions:
            return MotionInfo(None)
        idx = min(len(next_positions) - 1, count - 1)
        return MotionInfo(next_positions[idx], motion_type=MotionType.LineWise)
