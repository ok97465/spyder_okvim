"""Confirmed substitutions through the real Ex prompt and editor undo stack."""

import pytest
from qtpy.QtCore import Qt

from spyder_okvim.executor.tests.test_substitute import (
    submit,
    substitute_bot as _substitute_bot,
)

substitute_bot = _substitute_bot


@pytest.mark.parametrize(
    "command, responses, expected, count",
    [
        ("%s/foo/long/gc", "a", "long long\n  long long\nlast", 4),
        ("%s/foo/long/gc", "ynl", "long foo\n  long foo\nlast", 2),
        ("%s/foo/long/c", "ny", "foo foo\n  long foo\nlast", 1),
        ("%s/foo/long/gc", "nnnn", "foo foo\n  foo foo\nlast", 0),
    ],
)
def test_confirmed_changes_are_one_undo(
    substitute_bot, command, responses, expected, count
):
    editor, status, commandline, qtbot = substitute_bot
    original = editor.toPlainText()
    submit(substitute_bot, command)
    assert editor.toPlainText() == original
    assert status.substitute_confirm is not None
    qtbot.keyClicks(commandline, responses)
    assert editor.toPlainText() == expected
    assert status.sub_mode is status.substitute_confirm is None
    assert status.msg_label.text().startswith(f"{count} substitutions")
    assert not editor.get_extra_selections("vim_substitute")
    if count:
        qtbot.keyClicks(commandline, "u")
        assert editor.toPlainText() == original
        qtbot.keyPress(commandline, Qt.Key_R, modifier=Qt.ControlModifier)
        assert editor.toPlainText() == expected
    else:
        assert not editor.document().isUndoAvailable()


def test_noop_targets_are_confirmed_without_undo(substitute_bot):
    editor, status, commandline, qtbot = substitute_bot
    submit(substitute_bot, "s/foo/foo/gc")
    qtbot.keyClicks(commandline, "y")
    assert status.substitute_confirm is not None
    qtbot.keyClicks(commandline, "y")
    assert status.substitute_confirm is None
    assert status.msg_label.text().startswith("2 substitutions on 1 lines")
    assert not editor.document().isUndoAvailable()


@pytest.mark.parametrize(
    "responses, line, column",
    [
        ("yyyy", 1, 0),
        ("nnny", 1, 0),
        ("ynl", 1, 0),
        ("ynnn", 1, 6),
        ("ynq", 1, 2),
        ("a", 1, 2),
    ],
)
def test_confirmation_leaves_cursor_at_vim_completion_position(
    substitute_bot, responses, line, column
):
    """Vim distinguishes the last answer from earlier accepted matches."""
    editor, _, commandline, qtbot = substitute_bot
    submit(substitute_bot, "%s/foo/long/gc")
    qtbot.keyClicks(commandline, responses)
    cursor = editor.textCursor()
    assert (cursor.blockNumber(), cursor.positionInBlock()) == (line, column)


def test_count_overrides_confirmation(substitute_bot):
    editor, status, _, _ = substitute_bot
    original = editor.toPlainText()
    submit(substitute_bot, r"%s/foo/\r/gnc")
    assert status.substitute_confirm is None
    assert status.msg_label.text().startswith("4 matches")
    assert editor.toPlainText() == original


def test_confirmation_keeps_prior_and_later_changes_separate(substitute_bot):
    editor, _, commandline, qtbot = substitute_bot
    original = editor.toPlainText()
    qtbot.keyClicks(commandline, "x")
    before = editor.toPlainText()
    submit(substitute_bot, "%s/foo/long/gc")
    qtbot.keyClicks(commandline, "a")
    replaced = editor.toPlainText()
    qtbot.keyClicks(commandline, "x")
    for expected in (replaced, before, original):
        qtbot.keyClicks(commandline, "u")
        assert editor.toPlainText() == expected


def test_confirmation_validates_all_targets_before_prompting(substitute_bot):
    editor, status, _, _ = substitute_bot
    editor.set_text("a\n😀")
    submit(substitute_bot, r"%s/\C/x/gc")
    assert status.substitute_confirm is None
    assert status.last_substitute is None
    assert status.search.txt_searched == ""
    assert editor.toPlainText() == "a\n😀"
    assert not editor.document().isUndoAvailable()
