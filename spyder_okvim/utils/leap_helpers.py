# -*- coding: utf-8 -*-
"""Helper routines for Leap-style two-character motions."""

from __future__ import annotations

from typing import Callable

from qtpy.QtCore import QPoint
from qtpy.QtGui import QTextDocument

from spyder_okvim.utils.motion import MotionInfo, MotionType


class LeapHelper:
    """Expose operations that mimic ``leap.nvim`` behaviour."""

    def __init__(self, vim_status, set_motion_info: Callable[..., MotionInfo]):
        self.vim_status = vim_status
        self.get_editor = vim_status.get_editor
        self._set_motion_info = set_motion_info

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
        self.vim_status.annotate_on_txt(info_group, timeout=1500)

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
        self.vim_status.annotate_on_txt(info_group, timeout=1500)
