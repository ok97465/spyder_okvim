"""Compute Vim text-object ranges from a copied Qt document cursor.

Related quote, paragraph, word and bracket rules live together here. This module
neither edits the document nor owns mode, register, viewport or Spyder state.
Returned ranges use the MotionInfo endpoint conventions; unavailable objects
have no selection start/end.
"""

from __future__ import annotations

# Standard Libraries
import re
from bisect import bisect_left
from collections.abc import Callable

# Third Party Libraries
from qtpy.QtGui import QTextCursor

# Project Libraries
from spyder_okvim.utils.motion import MotionInfo, MotionType
from spyder_okvim.utils.qtcompat import python_cursor_position, qt_cursor_position

WHITE_SPACE = " \t"


class TextObjects:
    """Resolve related text objects against the current document on demand.

    The cursor provider is evaluated for each operation and must return a cursor
    for the active document. A copy is used throughout calculation, so movement
    and selection here cannot change the editor cursor or document. Methods run
    on the document's GUI thread and retain no request or editor lifetime state.
    """

    def __init__(self, get_cursor: Callable[[], QTextCursor]):
        self._get_cursor = get_cursor

    def _cursor(self) -> QTextCursor:
        """Return an independent cursor in the provider's current document."""
        return QTextCursor(self._get_cursor())

    def _character_at(self, position: int) -> str:
        """Read the Qt character at a UTF-16 position, or empty at document end."""
        cursor = self._cursor()
        if position >= cursor.document().characterCount() - 1:
            return ""
        cursor.setPosition(position)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
        return cursor.selectedText()

    def _character_before(self, position: int) -> str:
        """Read the Qt character preceding a UTF-16 position."""
        cursor = self._cursor()
        cursor.setPosition(position)
        cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor)
        return cursor.selectedText()

    def inner_quote(self, quote: str) -> MotionInfo:
        """Return line-local contents without quotes; backticks honor escapes."""
        if quote == "`":
            return self._backtick_object(around=False)
        sel_end = -1

        cursor = self._cursor()
        block = cursor.block()
        text = block.text()

        cursor_pos = python_cursor_position(text, cursor.positionInBlock())
        if self._character_at(cursor.position()) == quote:
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
                if sel_start >= 0:
                    sel_end = text.find(quote, sel_start + 1)
            else:
                sel_end = text.find(quote, cursor_pos)

        if sel_start > -1 and sel_end > -1:
            sel_start = block.position() + qt_cursor_position(text, sel_start + 1)
            sel_end = block.position() + qt_cursor_position(text, sel_end)
        else:
            sel_start = None
            sel_end = None

        return MotionInfo(None, sel_start, sel_end, motion_type=MotionType.BlockWise)

    def _include_trailing_white(self, pos_end: int) -> int:
        """Extend the exclusive UTF-16 end through horizontal whitespace."""
        cursor = self._cursor()

        cursor.setPosition(pos_end)

        # including trailing text
        if pos_end < cursor.document().characterCount() - 1 and not cursor.atBlockEnd():
            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
            ch = cursor.selectedText()

            cursor.setPosition(pos_end)
            if ch in WHITE_SPACE:
                cursor.movePosition(QTextCursor.NextWord)
                pos_end = cursor.position()

        return pos_end

    def _include_leading_white(self, pos_start: int) -> int:
        """Extend the UTF-16 start over adjacent leading whitespace."""
        cursor = self._cursor()
        cursor.setPosition(pos_start)
        document = cursor.document()
        block_start = cursor.block().position()
        while (
            pos_start > block_start
            and document.characterAt(pos_start - 1) in WHITE_SPACE
        ):
            pos_start -= 1
        return pos_start

    def _whitespace_range(self, cursor: QTextCursor) -> tuple[int, int]:
        """Return the current horizontal whitespace run in document coordinates."""
        start = self._include_leading_white(cursor.position())
        end = cursor.position()
        document = cursor.document()
        block_end = cursor.block().position() + cursor.block().length() - 1
        while end < block_end and document.characterAt(end) in WHITE_SPACE:
            end += 1
        return start, end

    def around_quote(self, quote: str) -> MotionInfo:
        """Include delimiters and adjacent space, preferring trailing space."""
        if quote == "`":
            return self._backtick_object(around=True)

        inner = self.inner_quote(quote)
        if inner.sel_start is None:
            return inner

        sel_start = inner.sel_start - 1
        quote_end = inner.sel_end + 1
        sel_end = self._include_trailing_white(quote_end)
        if sel_end == quote_end:
            sel_start = self._include_leading_white(sel_start)

        return MotionInfo(None, sel_start, sel_end, motion_type=MotionType.BlockWise)

    def _backtick_object(self, around: bool) -> MotionInfo:
        """Find a line-local backtick pair, ignoring escaped delimiters."""
        cursor = self._cursor()
        block = cursor.block()
        text = block.text()
        # QTextCursor positions count UTF-16 code units, including surrogate pairs.
        positions = []
        offset = block.position()
        backslashes = 0
        for char in text:
            if char == "`" and backslashes % 2 == 0:
                positions.append(offset)
            backslashes = backslashes + 1 if char == "\\" else 0
            offset += 2 if ord(char) > 0xFFFF else 1

        current = cursor.position()
        index = bisect_left(positions, current)
        if index < len(positions) and positions[index] == current:
            # On a delimiter, pair quotes from the start of the line. Between
            # delimiters, select the immediately surrounding pair instead.
            index -= index % 2
        else:
            index = max(0, index - 1)
        if index + 1 >= len(positions):
            return MotionInfo(None, motion_type=MotionType.BlockWise)

        start, end = positions[index : index + 2]
        if around:
            end += 1
            document = cursor.document()
            block_end = block.position() + block.length() - 1
            trailing_end = end
            while end < block_end and document.characterAt(end) in WHITE_SPACE:
                end += 1
            if end == trailing_end:
                while (
                    start > block.position()
                    and document.characterAt(start - 1) in WHITE_SPACE
                ):
                    start -= 1
        else:
            start += 1
        return MotionInfo(None, start, end, motion_type=MotionType.BlockWise)

    def _paragraph_object(self, count: int, around: bool) -> MotionInfo:
        """Select paragraph/blank-line runs without scanning unrelated blocks."""
        block = self._cursor().block()
        starts_blank = not block.text().strip()
        start = block
        while start.previous().isValid():
            previous = start.previous()
            if (not previous.text().strip()) != starts_blank:
                break
            start = previous

        end = start
        if around and starts_blank:
            while end.isValid() and not end.text().strip():
                end = end.next()
            if not end.isValid():
                return MotionInfo(None)

        for index in range(max(1, count)):
            blank = not end.text().strip()
            while end.next().isValid():
                following = end.next()
                if (not following.text().strip()) != blank:
                    break
                end = following
            if index + 1 < count:
                end = end.next()
                if around:
                    while end.isValid() and not end.text().strip():
                        end = end.next()
                if not end.isValid():
                    return MotionInfo(None)

        if around and not starts_blank:
            following = end.next()
            if following.isValid() and not following.text().strip():
                while following.isValid() and not following.text().strip():
                    end = following
                    following = following.next()
            else:
                previous = start.previous()
                while previous.isValid() and not previous.text().strip():
                    start = previous
                    previous = previous.previous()

        return MotionInfo(
            start.position(),
            start.position(),
            end.position() + end.length() - 1,
            motion_type=MotionType.LineWise,
        )

    def inner_paragraph(self, count: int = 1) -> MotionInfo:
        """Select paragraph contents or the current run of blank lines."""
        return self._paragraph_object(count, around=False)

    def around_paragraph(self, count: int = 1) -> MotionInfo:
        """Select paragraphs with adjacent blank lines."""
        return self._paragraph_object(count, around=True)

    def around_WORD(self, count: int = 1) -> MotionInfo:
        """Select whitespace-delimited WORDs with adjacent horizontal space."""
        cursor = self._cursor()
        document = cursor.document()
        document_end = document.characterCount() - 1
        start = cursor.position()

        def is_space(position):
            return document.characterAt(position).isspace()

        block_start = cursor.block().position()
        starts_space = is_space(start)
        while start > block_start and is_space(start - 1) == starts_space:
            start -= 1

        end = start
        ends_space = False
        for index in range(max(1, count)):
            if index:
                block = document.findBlock(end)
                # The previous WORD excludes its line separator. Cross it
                # before choosing the next WORD or whitespace object.
                if end == block.position() + block.length() - 1:
                    end += 1
            if end >= document_end:
                return MotionInfo(None, motion_type=MotionType.BlockWise)

            leading_space = is_space(end)
            if leading_space:
                # As in Vim's E motion, advance at least once, then stop at
                # the next empty line instead of consuming every blank line.
                end += 1
                while end <= document_end and is_space(end):
                    if document.findBlock(end).length() == 1:
                        break
                    end += 1
                if end > document_end:
                    return MotionInfo(None, motion_type=MotionType.BlockWise)

            while end < document_end and not is_space(end):
                end += 1
            word_end = end
            if not leading_space:
                while end < document_end and document.characterAt(end) in WHITE_SPACE:
                    end += 1
            ends_space = end > word_end or document.findBlock(end).length() == 1

        if not starts_space and not ends_space:
            leading_start = start
            while leading_start > block_start and is_space(leading_start - 1):
                leading_start -= 1
            if leading_start > block_start:
                start = leading_start

        return MotionInfo(None, start, end, motion_type=MotionType.BlockWise)

    def inner_word(self, count: int) -> MotionInfo:
        """Return the inner word/whitespace object for the counted selection."""
        cursor = self._cursor()

        initial_selection_start = cursor.position()

        if self._character_at(cursor.position()) in WHITE_SPACE:
            sel_start, sel_end = self._whitespace_range(cursor)
            cursor.setPosition(sel_end)
            count -= 1
        else:
            cursor.movePosition(QTextCursor.EndOfWord)
            cursor.movePosition(QTextCursor.StartOfWord)

            # For "abc.dd" at 0 position of cursor
            if initial_selection_start < cursor.position():
                cursor.movePosition(QTextCursor.Left)
                cursor.movePosition(QTextCursor.StartOfWord)

            sel_start = cursor.position()

        for idx in range(count):
            if idx % 2 == 0:
                cursor.movePosition(QTextCursor.EndOfWord)
            else:
                # go to the end of blank
                if cursor.atBlockEnd():
                    cursor.movePosition(QTextCursor.NextWord, n=2)
                else:
                    cursor.movePosition(QTextCursor.NextWord)

        sel_end = cursor.position()

        return MotionInfo(None, sel_start, sel_end, motion_type=MotionType.BlockWise)

    def inner_WORD(self, count: int) -> MotionInfo:
        """Return a counted whitespace-delimited inner WORD object."""
        cursor = self._cursor()

        if self._character_at(cursor.position()) in WHITE_SPACE:
            sel_start, sel_end = self._whitespace_range(cursor)
            cursor.setPosition(sel_end)
            count -= 1
        else:
            cursor.movePosition(QTextCursor.EndOfWord)
            cursor.movePosition(QTextCursor.StartOfWord)

            while (
                not cursor.atBlockStart()
                and self._character_before(cursor.position()) not in WHITE_SPACE
            ):
                cursor.movePosition(QTextCursor.Left)
                cursor.movePosition(QTextCursor.StartOfWord)

            sel_start = cursor.position()

        for idx in range(count):
            if idx % 2 == 0:
                if cursor.atBlockEnd():
                    cursor.movePosition(QTextCursor.NextWord, n=2)
                else:
                    cursor.movePosition(QTextCursor.EndOfWord)
                    while (
                        not cursor.atBlockEnd()
                        and self._character_at(cursor.position()) not in WHITE_SPACE
                    ):
                        cursor.movePosition(QTextCursor.Right)
                        if self._character_at(cursor.position()) not in WHITE_SPACE:
                            cursor.movePosition(QTextCursor.EndOfWord)
            else:
                # go to the end of blank
                if cursor.atBlockEnd():
                    cursor.movePosition(QTextCursor.NextWord, n=2)
                else:
                    cursor.movePosition(QTextCursor.NextWord)

        sel_end = cursor.position()

        return MotionInfo(None, sel_start, sel_end, motion_type=MotionType.BlockWise)

    def around_word(self, count: int) -> MotionInfo:
        """Return counted words with their adjacent whitespace."""
        cursor = self._cursor()

        initial_selection_start = cursor.position()

        is_trailing_space = True

        if self._character_at(cursor.position()) in WHITE_SPACE:
            sel_start, _ = self._whitespace_range(cursor)
            cursor.movePosition(QTextCursor.NextWord)
            cursor.movePosition(QTextCursor.EndOfWord)
            is_trailing_space = False
            count -= 1
        else:
            cursor.movePosition(QTextCursor.EndOfWord)
            cursor.movePosition(QTextCursor.StartOfWord)

            # For "abc.dd" at 0 position of cursor
            if initial_selection_start < cursor.position():
                cursor.movePosition(QTextCursor.Left)
                cursor.movePosition(QTextCursor.StartOfWord)

            sel_start = cursor.position()

        if is_trailing_space:
            for idx in range(count):
                if cursor.atBlockEnd():
                    # TODO : Fix the case that the line has leading space.
                    cursor.movePosition(QTextCursor.NextWord, n=2)
                else:
                    cursor.movePosition(QTextCursor.NextWord)
        else:
            for idx in range(count):
                block = cursor.block()
                text = block.text()
                if (
                    qt_cursor_position(text, len(text.rstrip()))
                    == cursor.positionInBlock()
                ):
                    cursor.movePosition(QTextCursor.NextBlock)
                    cursor.movePosition(QTextCursor.StartOfLine)
                    if self._character_at(cursor.position()) in WHITE_SPACE:
                        cursor.movePosition(QTextCursor.NextWord)
                    cursor.movePosition(QTextCursor.EndOfWord)
                else:
                    cursor.movePosition(QTextCursor.NextWord)
                    cursor.movePosition(QTextCursor.EndOfWord)

        sel_end = cursor.position()

        return MotionInfo(None, sel_start, sel_end, motion_type=MotionType.BlockWise)

    def bracket_range(
        self, count: int, bracket: str, position: int
    ) -> tuple[int | None, int | None]:
        """Return a paired bracket's half-open range, or (None, None).

        ``position`` uses Qt document coordinates. ``count`` is retained for
        the command contract but currently does not expand nested brackets.
        """
        bracket_patterns = {
            "(": ["(", ")", r"[()]"],
            ")": ["(", ")", r"[()]"],
            "[": ["[", "]", r"[\[\]]"],
            "]": ["[", "]", r"[\[\]]"],
            "{": ["{", "}", r"[{}]"],
            "}": ["{", "}", r"[{}]"],
        }
        opening, closing, bracket_pattern = bracket_patterns[bracket]
        text = self._cursor().document().toPlainText()
        position = python_cursor_position(text, position)

        sel_start = None
        sel_end = None

        pattern = re.compile(bracket_pattern)

        # Find position of close bracket
        if text[position : position + 1] == closing:
            sel_end = position + 1
        else:
            opening_depth = 0
            for match in pattern.finditer(text[position + 1 : :]):
                ch = match.group()
                if ch == opening:
                    opening_depth += 1
                else:
                    if opening_depth > 0:
                        opening_depth -= 1
                    else:
                        sel_end = match.start() + position + 1 + 1
                        break

        # Find position of open bracket
        if sel_end is None:
            return None, None
        if text[position : position + 1] == opening:
            sel_start = position
        else:
            closing_depth = 0
            for idx, ch in enumerate(reversed(text[:position])):
                if ch == closing:
                    closing_depth += 1
                elif ch == opening:
                    if closing_depth > 0:
                        closing_depth -= 1
                    else:
                        sel_start = position - idx - 1
                        break

        if sel_start is None or sel_end is None:
            return None, None
        return qt_cursor_position(text, sel_start), qt_cursor_position(text, sel_end)

    def around_bracket(self, count: int, bracket: str) -> MotionInfo:
        """Return the surrounding bracket range, including both delimiters."""
        cursor = self._cursor()
        cursor_pos = cursor.position()
        sel_start, sel_end = self.bracket_range(count, bracket, cursor_pos)

        if sel_start is None:
            # There are an open bracket after the cursor on the same line.
            open_bracket = {"(": "(", ")": "(", "[": "[", "]": "[", "{": "{", "}": "{"}[
                bracket
            ]
            block = cursor.block()
            text = block.text()
            block_pos = block.position()

            position_in_block = python_cursor_position(text, cursor_pos - block_pos)
            open_index = text.find(open_bracket, position_in_block)
            if open_index >= 0:
                open_bracket_pos = block_pos + qt_cursor_position(text, open_index)
                sel_start, sel_end = self.bracket_range(
                    count, bracket, open_bracket_pos
                )

        return MotionInfo(None, sel_start, sel_end, motion_type=MotionType.BlockWise)

    def inner_bracket(self, count: int, bracket: str) -> MotionInfo:
        """Return the range inside matching brackets, excluding delimiters."""
        motion_info = self.around_bracket(count, bracket)
        if motion_info.sel_start is not None and motion_info.sel_end is not None:
            motion_info.sel_start += 1
            motion_info.sel_end -= 1
            if motion_info.sel_start == motion_info.sel_end:
                motion_info.sel_start = None
                motion_info.sel_end = None

        return motion_info
