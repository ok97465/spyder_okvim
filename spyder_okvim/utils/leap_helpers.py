"""Helper routines for Leap-style two-character motions."""

from __future__ import annotations

# Standard Libraries
from collections import OrderedDict
from collections.abc import Iterator

# Third Party Libraries
from qtpy.QtCore import QPoint
from qtpy.QtGui import QTextCursor, QTextDocument

# Project Libraries
from spyder_okvim.utils.motion import MotionInfo, MotionType


class LeapHelper:
    """Expose operations that mimic ``leap.nvim`` behaviour."""

    _LABEL_BASE = "sfnjklhodweimbuyvrgtaqpcxzSFNJKLHODWEIMBUYVRGTAQPCXZ"

    def __init__(self, vim_status):
        self.vim_status = vim_status
        self.get_editor = vim_status.get_editor
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
            match_start = cursor.selectionStart()
            if match_start > view_end:
                break
            if match_start >= view_start:
                target = QTextCursor(doc)
                target.setPosition(match_start)
                if editor.cursorRect(target).intersects(editor.viewport().rect()):
                    positions.append(match_start)
            # Keep overlapping targets, advancing by one complete Qt character.
            cursor.setPosition(match_start)
            cursor.movePosition(QTextCursor.NextCharacter)
            start_pos = cursor.position()

        return sorted(positions)

    def _order_positions(
        self, positions: list[int], *, reverse: bool = False
    ) -> list[int]:
        """Return positions ordered relative to the current cursor."""
        if not positions:
            return []

        cursor_pos = self.get_editor().textCursor().position()
        if reverse:
            before = sorted(
                (pos for pos in positions if pos < cursor_pos), reverse=True
            )
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
    ) -> tuple[int, int]:
        """Show preview markers for the first typed character."""
        if not char:
            return 0, 0
        positions = self.search_in_view(char, reverse=reverse, full_view=full_view)
        max_annotations = self.vim_status.n_annotate_max
        limited_positions = positions[:max_annotations]
        if not limited_positions:
            self._preview_labels_by_pos.clear()
            self.vim_status.hide_annotate_on_txt()
            return len(positions), 0

        doc = self.get_editor().document()
        preview_mapping = self._build_preview_label_map(limited_positions, doc)
        self._preview_labels_by_pos = preview_mapping

        info_group = {
            self._label_anchor_position(doc, pos): label
            for pos, label in preview_mapping.items()
        }
        if info_group:
            displayed = self.vim_status.annotate_on_txt(info_group)
        else:
            self.vim_status.hide_annotate_on_txt()
            displayed = set()
        return len(positions), len(displayed)

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
        # Reserve uppercase prefixes for two-key labels. No complete label is
        # a prefix of another, so every displayed target can be selected.
        for ch in base.lower()[: len(base) // 2]:
            yield ch
        for first in base[len(base) // 2 :]:
            for second in base:
                yield f"{first}{second}"

    def _next_label(self, label_stream: Iterator[str], used_labels: set[str]) -> str:
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
        first, next_pos = self._character_at(doc, pos)
        second, _ = self._character_at(doc, next_pos)
        return f"{first}{second}"

    def _character_at(self, doc: QTextDocument, pos: int) -> tuple[str, int]:
        """Read one character without splitting a UTF-16 surrogate pair."""
        if pos < 0 or pos >= doc.characterCount() - 1:
            return "", pos
        cursor = QTextCursor(doc)
        cursor.setPosition(pos)
        cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
        return cursor.selectedText().replace("\u2029", "\n"), cursor.position()

    def _label_anchor_position(self, doc: QTextDocument, pos: int) -> int:
        """Return the position where the label should be displayed."""
        _, next_pos = self._character_at(doc, pos)
        _, anchor = self._character_at(doc, next_pos)
        return min(anchor, max(doc.characterCount() - 1, 0))

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

    def show_label_map(
        self, label_map: OrderedDict[str, int], *, preserve_positions=False
    ) -> OrderedDict[str, int]:
        """Display nearby labels and return only the targets that actually fit."""
        doc = self.get_editor().document()
        info_group = {
            self._label_anchor_position(doc, pos): label
            for label, pos in label_map.items()
        }
        if info_group:
            displayed = self.vim_status.annotate_on_txt(
                info_group, preserve_positions=preserve_positions
            )
            return OrderedDict(
                (label, pos)
                for label, pos in label_map.items()
                if self._label_anchor_position(doc, pos) in displayed
            )
        else:
            self.vim_status.hide_annotate_on_txt()
            return OrderedDict()

    # ------------------------------------------------------------------
    # Leap motions
    # ------------------------------------------------------------------
    def leap(
        self,
        chars: str,
        count: int = 1,
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
            pos = positions[(count - 1) % len(positions)]
        return MotionInfo(pos, motion_type=MotionType.CharWise)

    def display_additional_leap_targets(self) -> None:
        """Show annotations for additional Leap targets."""
        full_view = self.vim_status.find_info.cmd_name in {"s", "S"}
        positions = self.search_in_view(
            self.vim_status.find_info.ch, full_view=full_view
        )
        info_group = {
            self._label_anchor_position(self.get_editor().document(), pos): (
                f"{idx};" if idx != 1 else ";"
            )
            for idx, pos in enumerate(positions, 1)
        }
        self.vim_status.annotate_on_txt(info_group)

    def reverse_leap(
        self,
        chars: str,
        count: int = 1,
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
            pos = positions[(count - 1) % len(positions)]
        return MotionInfo(pos, motion_type=MotionType.CharWise)

    def display_additional_reverse_leap_targets(self) -> None:
        """Show annotations for additional reverse Leap targets."""
        full_view = self.vim_status.find_info.cmd_name in {"s", "S"}
        positions = self.search_in_view(
            self.vim_status.find_info.ch, reverse=True, full_view=full_view
        )
        info_group = {
            self._label_anchor_position(self.get_editor().document(), pos): (
                f"{idx};" if idx != 1 else ";"
            )
            for idx, pos in enumerate(positions, 1)
        }
        self.vim_status.annotate_on_txt(info_group)
