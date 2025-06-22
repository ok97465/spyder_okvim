from __future__ import annotations

from bisect import bisect_left, bisect_right
from typing import Callable

from qtpy.QtCore import QPoint, QRegularExpression
from qtpy.QtGui import QTextCursor, QTextDocument
from qtpy.QtWidgets import QTextEdit
from spyder.config.manager import CONF

from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.utils.motion import MotionInfo, MotionType


class SearchHelper:
    """Helper routines for search-related motions."""

    def __init__(self, vim_status, set_motion_info: Callable[..., MotionInfo]):
        self.vim_status = vim_status
        self.get_editor = vim_status.get_editor
        self.get_cursor = vim_status.get_cursor
        self._set_motion_info = set_motion_info

    # ------------------------------------------------------------------
    # Viewport helpers
    # ------------------------------------------------------------------
    def get_viewport_positions(self) -> tuple[int, int]:
        """Return start and end character positions of the visible viewport."""
        editor = self.get_editor()
        start_pos = editor.cursorForPosition(QPoint(0, 0)).position()
        bottom_right = QPoint(
            editor.viewport().width() - 1, editor.viewport().height() - 1
        )
        end_pos = editor.cursorForPosition(bottom_right).position()
        return start_pos, end_pos

    def search_forward_in_view(self, text: str) -> list[int]:
        """Return cursor positions of ``text`` inside the viewport."""
        editor = self.get_editor()
        cur_pos = editor.textCursor().position()
        view_start, view_end = self.get_viewport_positions()
        start_pos = min(view_end, cur_pos) + 1
        positions: list[int] = []
        while view_start <= start_pos <= view_end:
            cursor = editor.document().find(text, start_pos, QTextDocument.FindCaseSensitively)
            if cursor.isNull() or cursor.position() > view_end:
                break
            positions.append(cursor.position() - len(text))
            start_pos = cursor.position()
        return positions

    def search_backward_in_view(self, text: str) -> list[int]:
        """Return positions of ``text`` when searching backward in the viewport."""
        editor = self.get_editor()
        cur_pos = editor.textCursor().position()
        view_start, view_end = self.get_viewport_positions()
        start_pos = min(view_end, cur_pos)
        positions: list[int] = []
        while view_start <= start_pos <= view_end:
            cursor = editor.document().find(
                text,
                start_pos,
                QTextDocument.FindCaseSensitively | QTextDocument.FindBackward,
            )
            if cursor.isNull() or cursor.position() < view_start:
                break
            positions.append(cursor.position() - len(text))
            start_pos = cursor.position() - len(text) - 1
        return positions

    # ------------------------------------------------------------------
    # Sneak motions
    # ------------------------------------------------------------------
    def sneak(self, chars: str, num: int = 1, by_repeat_cmd: bool = False) -> MotionInfo:
        """Jump forward to the given two-character sequence within the viewport."""
        if not by_repeat_cmd:
            self.vim_status.find_info.set("s", chars)
        pos = None
        positions = self.search_forward_in_view(chars)
        if positions:
            pos = positions[(num - 1) % len(positions)]
        return self._set_motion_info(pos, motion_type=MotionType.CharWise)

    def display_another_group_after_sneak(self) -> None:
        """Show annotations for additional sneak targets."""
        positions = self.search_forward_in_view(self.vim_status.find_info.ch)
        info_group = {pos + 1: f"{idx};" if idx != 1 else ";" for idx, pos in enumerate(positions, 1)}
        self.vim_status.annotate_on_txt(info_group, timeout=1500)

    def rsneak(self, chars: str, num: int = 1, by_repeat_cmd: bool = False) -> MotionInfo:
        """Jump backward to the given two-character sequence within the viewport."""
        if not by_repeat_cmd:
            self.vim_status.find_info.set("S", chars)
        pos = None
        positions = self.search_backward_in_view(chars)
        if positions:
            pos = positions[(num - 1) % len(positions)]
        return self._set_motion_info(pos, motion_type=MotionType.CharWise)

    def display_another_group_after_rsneak(self) -> None:
        """Show annotations for additional reverse sneak targets."""
        positions = self.search_backward_in_view(self.vim_status.find_info.ch)
        info_group = {pos + 1: f"{idx};" if idx != 1 else ";" for idx, pos in enumerate(positions, 1)}
        self.vim_status.annotate_on_txt(info_group, timeout=1500)

    # ------------------------------------------------------------------
    # Search in document
    # ------------------------------------------------------------------
    def search(self, text: str) -> None:
        """Highlight all occurrences of ``text`` in the document."""
        editor = self.get_editor()
        cursor = QTextCursor(editor.document())
        cursor.movePosition(QTextCursor.Start)

        is_ignorecase = CONF.get(CONF_SECTION, "ignorecase")
        is_smartcase = CONF.get(CONF_SECTION, "smartcase")

        option = None
        if is_ignorecase:
            self.vim_status.search.ignorecase = True
            if is_smartcase and text.lower() != text:
                option = QTextDocument.FindCaseSensitively
                self.vim_status.search.ignorecase = False
        else:
            option = QTextDocument.FindCaseSensitively
            self.vim_status.search.ignorecase = False

        back = self.vim_status.search.color_bg
        fore = self.vim_status.search.color_fg
        search_stack = []
        while True:
            if option:
                cursor = editor.document().find(QRegularExpression(text), cursor, options=option)
            else:
                cursor = editor.document().find(QRegularExpression(text), cursor)

            if cursor.position() != -1:
                selection = QTextEdit.ExtraSelection()
                selection.format.setBackground(back)
                selection.format.setForeground(fore)
                selection.cursor = cursor
                search_stack.append(selection)
            else:
                break

        self.vim_status.cursor.set_extra_selections("vim_search", [i for i in search_stack])
        self.vim_status.search.selection_list = search_stack
        self.vim_status.search.txt_searched = text

    def n(self, num: int = 1, num_str: str = "") -> MotionInfo:
        """Move to the next search match."""
        positions = self.vim_status.search.get_sel_start_list()
        if not positions:
            return self._set_motion_info(None)
        text = self.vim_status.search.txt_searched
        self.vim_status.set_message(f"/{text}")
        cursor_pos = self.get_cursor().position()
        idx = bisect_right(positions, cursor_pos)
        if idx == len(positions):
            idx = 0
        idx = (idx + num - 1) % len(positions)
        return self._set_motion_info(positions[idx], motion_type=MotionType.CharWise)

    def N(self, num: int = 1, num_str: str = "") -> MotionInfo:
        """Move to the previous search match."""
        positions = self.vim_status.search.get_sel_start_list()
        if not positions:
            return self._set_motion_info(None)
        text = self.vim_status.search.txt_searched
        self.vim_status.set_message(f"?{text}")
        cursor_pos = self.get_cursor().position()
        idx = bisect_left(positions, cursor_pos)
        idx = (idx - (num - 1)) % len(positions)
        return self._set_motion_info(positions[idx - 1], motion_type=MotionType.CharWise)

    # ------------------------------------------------------------------
    # Word searches
    # ------------------------------------------------------------------
    def _get_word_under_cursor(self) -> str | None:
        editor = self.get_editor()
        return editor.get_current_word()

    def asterisk(self, num: int = 1, num_str: str = "") -> MotionInfo:
        """Search forward for the word under the cursor."""
        word = self._get_word_under_cursor()
        if word is None:
            return self._set_motion_info(None)
        self.search(fr"\b{word}\b")
        return self.n(num=num)

    def sharp(self, num: int = 1, num_str: str = "") -> MotionInfo:
        """Search backward for the word under the cursor."""
        word = self._get_word_under_cursor()
        if word is None:
            return self._set_motion_info(None)
        self.search(fr"\b{word}\b")
        return self.N(num=num)
