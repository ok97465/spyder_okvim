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

    def search_forward_in_view(self, text: str) -> list[int]:
        """Return cursor positions of ``text`` inside the viewport."""
        editor = self.get_editor()
        cur_pos = editor.textCursor().position()
        view_start, view_end = self.get_viewport_positions()
        start_pos = min(view_end, cur_pos) + 1
        positions: list[int] = []
        while view_start <= start_pos <= view_end:
            cursor = editor.document().find(
                text,
                start_pos,
                QTextDocument.FindCaseSensitively,
            )
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

    def preview_first_char(self, char: str, reverse: bool) -> None:
        """Show preview markers for the first typed character."""
        if not char:
            return
        positions = (
            self.search_backward_in_view(char)
            if reverse
            else self.search_forward_in_view(char)
        )
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
    ) -> MotionInfo:
        """Jump forward to the given two-character sequence within the viewport."""
        if not by_repeat_cmd:
            self.vim_status.find_info.set("l", chars)
        positions = self.search_forward_in_view(chars)
        pos = None
        if positions:
            pos = positions[(num - 1) % len(positions)]
        return self._set_motion_info(pos, motion_type=MotionType.CharWise)

    def display_additional_leap_targets(self) -> None:
        """Show annotations for additional Leap targets."""
        positions = self.search_forward_in_view(self.vim_status.find_info.ch)
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
    ) -> MotionInfo:
        """Jump backward to the given two-character sequence within the viewport."""
        if not by_repeat_cmd:
            self.vim_status.find_info.set("L", chars)
        positions = self.search_backward_in_view(chars)
        pos = None
        if positions:
            pos = positions[(num - 1) % len(positions)]
        return self._set_motion_info(pos, motion_type=MotionType.CharWise)

    def display_additional_reverse_leap_targets(self) -> None:
        """Show annotations for additional reverse Leap targets."""
        positions = self.search_backward_in_view(self.vim_status.find_info.ch)
        info_group = {
            pos + 1: f"{idx};" if idx != 1 else ";"
            for idx, pos in enumerate(positions, 1)
        }
        self.vim_status.annotate_on_txt(info_group)
