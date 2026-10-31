# -*- coding: utf-8 -*-
"""Tests for Leap viewport-wide searches."""

from __future__ import annotations

# Standard Libraries
from types import SimpleNamespace

# Third Party Libraries
import pytest
from qtpy.QtWidgets import QPlainTextEdit

# Project Libraries
from spyder_okvim.utils.leap_helpers import LeapHelper
from tests.qt_support import reset_vim_state


def _set_editor_text(editor, qtbot, text: str) -> None:
    """Set editor text and wait until the document reflects it."""
    editor.set_text(text)
    editor.highlighter.rehighlight()
    qtbot.waitUntil(lambda: editor.toPlainText() == text, timeout=2000)


@pytest.mark.parametrize(
    "text,query,expected",
    [("x aaa", "aa", [2, 3]), ("x 😀😀😀", "😀😀", [2, 4])],
)
def test_leap_includes_overlapping_targets(qtbot, text, query, expected):
    """A two-character target can begin inside the preceding match."""
    editor = QPlainTextEdit(text)
    qtbot.addWidget(editor)
    editor.resize(600, 200)
    editor.show()
    helper = LeapHelper(SimpleNamespace(get_editor=lambda: editor))

    assert helper.search_in_view(query, full_view=True) == expected
    assert helper.search_in_view(query, reverse=True, full_view=True) == expected[::-1]


def test_search_in_view_covers_full_viewport(vim_bot):
    """Ensure s/S searches consider every viewport occurrence."""
    _, _, editor, vim, qtbot = vim_bot
    vim_status = vim.vim_cmd.vim_status
    helper_motion = vim.vim_cmd.executor_normal_cmd.helper_motion

    original_text = editor.toPlainText()
    new_text = "foo\nmiddle line\nfoo\nother middle\nfoo\n"

    try:
        _set_editor_text(editor, qtbot, new_text)
        reset_vim_state(vim_status)

        block = editor.document().findBlockByNumber(1)
        vim_status.cursor.set_cursor_pos(block.position())

        positions_forward = helper_motion.leap_helper.search_in_view(
            "fo", full_view=True
        )
        positions_reverse = helper_motion.leap_helper.search_in_view(
            "fo", reverse=True, full_view=True
        )

        expected_positions = []
        index = new_text.find("fo")
        while index != -1:
            expected_positions.append(index)
            index = new_text.find("fo", index + 1)

        assert positions_forward
        assert positions_reverse
        assert sorted(positions_forward) == expected_positions
        assert sorted(positions_reverse) == expected_positions

        cursor_pos = vim_status.get_cursor().position()
        after = [pos for pos in expected_positions if pos > cursor_pos]
        before = [pos for pos in expected_positions if pos <= cursor_pos]
        expected_forward = after[0] if after else expected_positions[0]
        expected_reverse = before[-1] if before else expected_positions[-1]

        assert positions_forward[0] == expected_forward
        assert positions_reverse[0] == expected_reverse

        motion_forward = helper_motion.leap_helper.leap(
            "fo", full_view=True, cmd_name="s"
        )
        motion_reverse = helper_motion.leap_helper.reverse_leap(
            "fo", full_view=True, cmd_name="S"
        )
        assert motion_forward.cursor_pos == expected_forward
        assert motion_reverse.cursor_pos == expected_reverse
    finally:
        _set_editor_text(editor, qtbot, original_text)
        reset_vim_state(vim_status)


def test_leap_uses_utf16_positions_and_anchors(vim_bot):
    """An emoji before/inside a target must not shift or split its label."""
    _, _, editor, vim, qtbot = vim_bot
    status = vim.vim_cmd.vim_status
    reset_vim_state(status)
    text = "x😀가나 😀가나"
    _set_editor_text(editor, qtbot, text)
    status.cursor.set_cursor_pos(0)
    helper = vim.vim_cmd.executor_normal_cmd.motions.leap_helper
    assert helper.search_in_view("😀가", full_view=True) == [1, 6]
    assert helper._get_pair_key(editor.document(), 1) == "😀가"
    assert helper._label_anchor_position(editor.document(), 1) == 4


def test_leap_labels_remain_selectable_and_stable(vim_bot):
    """Two-key labels have reserved prefixes and retain the preview assignment."""
    _, _, editor, vim, qtbot = vim_bot
    status = vim.vim_cmd.vim_status
    reset_vim_state(status)
    _set_editor_text(editor, qtbot, "x\n" + ("ab " * 7 + "\n") * 5)
    status.cursor.set_cursor_pos(0)
    helper = vim.vim_cmd.executor_normal_cmd.motions.leap_helper
    helper.preview_first_char("a", False, full_view=True)
    preview = dict(helper._preview_labels_by_pos)
    positions = helper.search_in_view("ab", full_view=True)
    labels = helper.build_label_map(positions)
    assert any(len(label) == 2 for label in labels)
    assert all(preview[position] == label for label, position in labels.items())
    assert not any(
        longer.startswith(shorter)
        for shorter in labels
        for longer in labels
        if shorter != longer
    )
