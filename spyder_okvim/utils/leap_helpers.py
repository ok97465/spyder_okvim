# -*- coding: utf-8 -*-
"""Helper routines for Leap-style two-character motions."""

from __future__ import annotations

from collections import OrderedDict
from typing import Callable, Iterator

from qtpy.QtCore import QPoint
from qtpy.QtGui import QTextDocument

from spyder_okvim.utils.motion import MotionInfo, MotionType


class LeapHelper:
    """Expose operations that mimic ``leap.nvim`` behaviour."""

    _LABEL_BASE = "abcdefghijklmnopqrstuvwxyz0123456789"

    def __init__(self, vim_status, set_motion_info: Callable[..., MotionInfo]):
        self.vim_status = vim_status
        self.get_editor = vim_status.get_editor
        self._set_motion_info = set_motion_info
        self._preview_labels_by_pos: OrderedDict[int, str] = OrderedDict()

    # ------------------------------------------------------------------
    # Viewport utilities
    # ------------------------------------------------------------------
    def get_viewport_positions(self) -> tuple[int, int]:
        """Return start and end character positions of the visible viewport."""
        editor = self.get_editor()
        start_pos = editor.cursorForPosition(QPoint(0, 0)).position()
        bottom_right = QPoint(
            editor.viewport().width() - 1,
            editor.viewport().height() - 1,
        )
        end_pos = editor.cursorForPosition(bottom_right).position()
        return start_pos, end_pos

    def _collect_viewport_matches(self, text: str) -> list[int]:
        """Return all match start positions for ``text`` inside the viewport."""
        if not text:
            return []

        editor = self.get_editor()
        view_start, view_end = self.get_viewport_positions()
        if view_start > view_end:
            return []

        doc = editor.document()
        positions: list[int] = []
        start_pos = view_start

        while start_pos <= view_end:
            cursor = doc.find(
                text,
                start_pos,
                QTextDocument.FindCaseSensitively,
            )
            if cursor.isNull():
                break
            match_end = cursor.position()
            match_start = match_end - len(text)
            if match_start > view_end:
                break
            if match_start >= view_start:
                positions.append(match_start)
            # Advance search cursor to avoid infinite loops on zero-width matches
            start_pos = max(match_end, match_start + 1)

        return sorted(positions)

    def _order_positions(
        self, positions: list[int], *, reverse: bool = False
    ) -> list[int]:
        """Return positions ordered relative to the current cursor."""
        if not positions:
            return []

        cursor_pos = self.get_editor().textCursor().position()
        if reverse:
            before = sorted((pos for pos in positions if pos < cursor_pos), reverse=True)
            after = sorted(
                (pos for pos in positions if pos >= cursor_pos), reverse=True
            )
            return before + after

        after = sorted(pos for pos in positions if pos > cursor_pos)
        before = sorted(pos for pos in positions if pos <= cursor_pos)
        return after + before

    def search_in_view(
        self,
        text: str,
        *,
        reverse: bool = False,
        full_view: bool = False,
    ) -> list[int]:
        """Return viewport positions of ``text`` ordered for the given direction."""
        positions = self._collect_viewport_matches(text)
        if not positions:
            return []

        cursor_pos = self.get_editor().textCursor().position()

        if not full_view:
            if reverse:
                filtered = [pos for pos in positions if pos < cursor_pos]
                return sorted(filtered, reverse=True)
            filtered = [pos for pos in positions if pos > cursor_pos]
            return sorted(filtered)

        return self._order_positions(positions, reverse=reverse)

    # ------------------------------------------------------------------
    # Preview helpers
    # ------------------------------------------------------------------
    def clear_overlays(self, *, preserve_preview: bool = False) -> None:
        """Remove any active Leap annotations.

        Args:
            preserve_preview: When ``True``, keep the preview label mapping so
                that follow-up stages can reuse the same labels.
        """
        if not preserve_preview:
            self._preview_labels_by_pos.clear()
        self.vim_status.hide_annotate_on_txt()

    def preview_first_char(
        self, char: str, reverse: bool, *, full_view: bool = False
    ) -> None:
        """Show preview markers for the first typed character."""
        if not char:
            return
        positions = self.search_in_view(char, reverse=reverse, full_view=full_view)
        max_annotations = self.vim_status.n_annotate_max
        limited_positions = positions[:max_annotations]
        if not limited_positions:
            self._preview_labels_by_pos.clear()
            self.vim_status.hide_annotate_on_txt()
            return

        doc = self.get_editor().document()
        preview_mapping = self._build_preview_label_map(limited_positions, doc)
        self._preview_labels_by_pos = preview_mapping

        info_group = {
            self._label_anchor_position(doc, pos): label
            for pos, label in preview_mapping.items()
        }
        if info_group:
            self.vim_status.annotate_on_txt(info_group)
        else:
            self.vim_status.hide_annotate_on_txt()

    def _build_preview_label_map(
        self, positions: list[int], doc: QTextDocument
    ) -> OrderedDict[int, str]:
        """Return per-position labels grouped by their two-character key."""
        preview: OrderedDict[int, str] = OrderedDict()
        for pos_list in self._group_positions_by_pair(positions, doc).values():
            label_stream = self._label_stream()
            used_labels: set[str] = set()
            for pos in pos_list:
                preview[pos] = self._next_label(label_stream, used_labels)
        return preview

    def _label_stream(self) -> Iterator[str]:
        """Yield label strings in the same order as ``leap.nvim``."""
        base = self._LABEL_BASE
        for ch in base:
            yield ch
        for first in base:
            for second in base:
                yield f"{first}{second}"

    def _next_label(
        self, label_stream: Iterator[str], used_labels: set[str]
    ) -> str:
        """Return the next label not present in ``used_labels``."""
        for label in label_stream:
            if label not in used_labels:
                used_labels.add(label)
                return label
        raise RuntimeError("Ran out of Leap labels")

    def _group_positions_by_pair(
        self, positions: list[int], doc: QTextDocument
    ) -> OrderedDict[str, list[int]]:
        """Return positions grouped by their two-character key."""
        group_map: OrderedDict[str, list[int]] = OrderedDict()
        for pos in positions:
            pair_key = self._get_pair_key(doc, pos)
            group_map.setdefault(pair_key, []).append(pos)

        return group_map

    def _get_pair_key(self, doc: QTextDocument, pos: int) -> str:
        """Return the two-character key starting at ``pos``."""
        first = self._char_from_doc(doc, pos)
        advance = max(len(first), 1)
        second = self._char_from_doc(doc, pos + advance)
        return f"{first}{second}"

    def _char_from_doc(self, doc: QTextDocument, pos: int) -> str:
        """Return the character at ``pos`` or empty string."""
        if pos < 0:
            return ""
        char = doc.characterAt(pos)
        if char is None:
            return ""
        text = str(char)
        if not text or text == "\x00":
            return ""
        return "\n" if text == "\u2029" else text

    def _label_anchor_position(self, doc: QTextDocument, pos: int) -> int:
        """Return the position where the label should be displayed."""
        first = self._char_from_doc(doc, pos)
        advance = max(len(first), 1)
        second = self._char_from_doc(doc, pos + advance)
        if second:
            advance += len(second)
        anchor = pos + advance
        char_count = max(doc.characterCount() - 1, 0)
        return min(anchor, char_count)

    def build_label_map(self, positions: list[int]) -> OrderedDict[str, int]:
        """Assign label strings to the given target positions."""
        limited = positions[: self.vim_status.n_annotate_max]
        mapping: OrderedDict[str, int] = OrderedDict()
        label_stream = self._label_stream()
        used_labels: set[str] = set()

        for pos in limited:
            label = self._preview_labels_by_pos.get(pos)
            if label and label not in used_labels:
                used_labels.add(label)
            else:
                label = self._next_label(label_stream, used_labels)
            mapping[label] = pos
        return mapping

    def show_label_map(self, label_map: OrderedDict[str, int]) -> None:
        """Display labels near targets."""
        doc = self.get_editor().document()
        info_group = {
            self._label_anchor_position(doc, pos): label
            for label, pos in label_map.items()
        }
        if info_group:
            self.vim_status.annotate_on_txt(info_group)
        else:
            self.vim_status.hide_annotate_on_txt()

    # ------------------------------------------------------------------
    # Leap motions
    # ------------------------------------------------------------------
    def leap(
        self,
        chars: str,
        num: int = 1,
        by_repeat_cmd: bool = False,
        *,
        full_view: bool = False,
        cmd_name: str | None = None,
    ) -> MotionInfo:
        """Jump forward to the given two-character sequence within the viewport."""
        if not by_repeat_cmd:
            name = cmd_name or ("s" if full_view else "l")
            self.vim_status.find_info.set(name, chars)
        positions = self.search_in_view(chars, full_view=full_view)
        pos = None
        if positions:
            pos = positions[(num - 1) % len(positions)]
        return self._set_motion_info(pos, motion_type=MotionType.CharWise)

    def display_additional_leap_targets(self) -> None:
        """Show annotations for additional Leap targets."""
        full_view = self.vim_status.find_info.cmd_name in {"s", "S"}
        positions = self.search_in_view(
            self.vim_status.find_info.ch, full_view=full_view
        )
        info_group = {
            pos + 1: f"{idx};" if idx != 1 else ";"
            for idx, pos in enumerate(positions, 1)
        }
        self.vim_status.annotate_on_txt(info_group)

    def reverse_leap(
        self,
        chars: str,
        num: int = 1,
        by_repeat_cmd: bool = False,
        *,
        full_view: bool = False,
        cmd_name: str | None = None,
    ) -> MotionInfo:
        """Jump backward to the given two-character sequence within the viewport."""
        if not by_repeat_cmd:
            name = cmd_name or ("S" if full_view else "L")
            self.vim_status.find_info.set(name, chars)
        positions = self.search_in_view(chars, reverse=True, full_view=full_view)
        pos = None
        if positions:
            pos = positions[(num - 1) % len(positions)]
        return self._set_motion_info(pos, motion_type=MotionType.CharWise)

    def display_additional_reverse_leap_targets(self) -> None:
        """Show annotations for additional reverse Leap targets."""
        full_view = self.vim_status.find_info.cmd_name in {"s", "S"}
        positions = self.search_in_view(
            self.vim_status.find_info.ch, reverse=True, full_view=full_view
        )
        info_group = {
            pos + 1: f"{idx};" if idx != 1 else ";"
            for idx, pos in enumerate(positions, 1)
        }
        self.vim_status.annotate_on_txt(info_group)
