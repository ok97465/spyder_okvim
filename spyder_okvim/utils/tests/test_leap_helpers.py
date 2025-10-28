# -*- coding: utf-8 -*-
"""Tests for Leap viewport-wide searches."""

from __future__ import annotations

def _set_editor_text(editor, qtbot, text: str) -> None:
    """Set editor text and wait until the document reflects it."""
    editor.set_text(text)
    editor.highlighter.rehighlight()
    qtbot.waitUntil(lambda: editor.toPlainText() == text, timeout=2000)


def test_search_in_view_covers_full_viewport(vim_bot):
    """Ensure s/S searches consider every viewport occurrence."""
    _, _, editor, vim, qtbot = vim_bot
    vim_status = vim.vim_cmd.vim_status
    helper_motion = vim.vim_cmd.executor_normal_cmd.helper_motion

    original_text = editor.toPlainText()
    new_text = "foo\nmiddle line\nfoo\nother middle\nfoo\n"

    try:
        _set_editor_text(editor, qtbot, new_text)
        vim_status.reset_for_test()

        block = editor.document().findBlockByNumber(1)
        vim_status.cursor.set_cursor_pos(block.position())

        positions_forward = helper_motion.search_in_view("fo", full_view=True)
        positions_reverse = helper_motion.search_in_view("fo", reverse=True, full_view=True)

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
        vim_status.reset_for_test()
