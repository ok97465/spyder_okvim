from __future__ import annotations

from bisect import bisect_left, bisect_right
from typing import Callable

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
    # Search in document
    # ------------------------------------------------------------------
    def search(self, text: str) -> None:
        """Highlight all occurrences of ``text`` in the document."""
        is_ignorecase = CONF.get(CONF_SECTION, "ignorecase")
        is_smartcase = CONF.get(CONF_SECTION, "smartcase")
        ignorecase = is_ignorecase and not (is_smartcase and text.lower() != text)
        self.vim_status.search.search(text, ignorecase=ignorecase)

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
        return self._set_motion_info(
            positions[idx - 1], motion_type=MotionType.CharWise
        )

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
        self.search(rf"\b{word}\b")
        return self.n(num=num)

    def sharp(self, num: int = 1, num_str: str = "") -> MotionInfo:
        """Search backward for the word under the cursor."""
        word = self._get_word_under_cursor()
        if word is None:
            return self._set_motion_info(None)
        self.search(rf"\b{word}\b")
        return self.N(num=num)
