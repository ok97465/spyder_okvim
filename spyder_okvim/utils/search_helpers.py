from __future__ import annotations

from bisect import bisect_left, bisect_right
from typing import Callable

from qtpy.QtCore import QRegularExpression

from spyder.config.manager import CONF

from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.utils.motion import MotionInfo, MotionType


def resolve_ignorecase(text: str, override: bool | None = None) -> bool:
    """Resolve search case settings without modifying global configuration."""
    if override is not None:
        return override
    ignorecase = CONF.get(CONF_SECTION, "ignorecase")
    smartcase = CONF.get(CONF_SECTION, "smartcase")
    return ignorecase and not (smartcase and text.lower() != text)


def compile_pattern(text: str, ignorecase: bool) -> QRegularExpression:
    """Create the expression shared by search and Ex substitution."""
    pattern = QRegularExpression(text)
    if ignorecase:
        pattern.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
    return pattern


def iter_block_matches(pattern, text: str, global_matches: bool = True):
    """Yield original Qt matches with UTF-16 offsets, including empty matches.

    Normalize NBSP for matching, as QTextDocument.find does. Consumers that
    expand captures should obtain their text from the unmodified paragraph.
    Qt's iterator owns empty-match advancement and same-start match ordering.
    """
    text = text.replace("\u00a0", " ")
    if global_matches:
        matches = pattern.globalMatch(text)
        while matches.hasNext():
            yield matches.next()
    else:
        match = pattern.match(text)
        if match.hasMatch():
            yield match


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
    def search(self, text: str, forward: bool = True) -> None:
        """Search in ``forward`` direction, reusing the previous pattern if empty."""
        text = text or self.vim_status.search.txt_searched
        if not text:
            return
        ignorecase = resolve_ignorecase(text)
        self.vim_status.search.search(text, ignorecase=ignorecase, forward=forward)

    def n(self, num: int = 1, num_str: str = "") -> MotionInfo:
        """Move to a match in the direction of the last search."""
        return self._repeat(num, self.vim_status.search.forward)

    def N(self, num: int = 1, num_str: str = "") -> MotionInfo:
        """Move to a match opposite the direction of the last search."""
        return self._repeat(num, not self.vim_status.search.forward)

    def _repeat(self, num: int, forward: bool) -> MotionInfo:
        """Find a counted match while preserving the saved search direction."""
        positions = self.vim_status.search.get_sel_start_list()
        if not positions:
            return self._set_motion_info(None)
        text = self.vim_status.search.txt_searched
        prefix = "/" if forward else "?"
        self.vim_status.set_message(f"{prefix}{text}")
        cursor_pos = self.get_cursor().position()
        if forward:
            idx = bisect_right(positions, cursor_pos) + num - 1
        else:
            idx = bisect_left(positions, cursor_pos) - num
        idx %= len(positions)
        return self._set_motion_info(positions[idx], motion_type=MotionType.CharWise)

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
        self.search(rf"\b{word}\b", forward=True)
        return self.n(num=num)

    def sharp(self, num: int = 1, num_str: str = "") -> MotionInfo:
        """Search backward for the word under the cursor."""
        word = self._get_word_under_cursor()
        if word is None:
            return self._set_motion_info(None)
        self.search(rf"\b{word}\b", forward=False)
        return self.n(num=num)
