"""Repeated Ex substitutions share values across modes and editor files."""

# Third Party Libraries
import pytest
from qtpy.QtCore import Qt

# Project Libraries
from tests.qt_support import reset_vim_state
from tests.qt_support import submit_substitution as submit


@pytest.mark.parametrize(
    "repeat, expected",
    [
        ("s", "x foo\nfoo foo"),
        ("&", "x foo\nfoo foo"),
        ("&&", "x x\nfoo foo"),
        ("&&g", "x foo\nfoo foo"),
        ("s g", "x x\nfoo foo"),
        ("&g 2", "x x\nx x"),
    ],
)
def test_repeat_flags_and_range_default(substitute_bot, repeat, expected):
    editor, status, _, _ = substitute_bot
    submit(substitute_bot, "%s/foo/x/g")
    editor.set_text("foo foo\nfoo foo")
    status.cursor.set_cursor_pos(0)
    status.search.search("unrelated")
    submit(substitute_bot, repeat)
    assert editor.toPlainText() == expected
    assert status.search.txt_searched == "foo"


def test_tilde_uses_latest_search_with_previous_replacement(substitute_bot):
    editor, status, _, _ = substitute_bot
    submit(substitute_bot, "s/foo/x/")
    editor.set_text("bar foo bar")
    status.cursor.set_cursor_pos(0)
    status.search.search("bar", forward=False)
    submit(substitute_bot, "~g")
    assert editor.toPlainText() == "x foo x"
    assert status.search.forward is False
    assert status.last_substitute.pattern == "bar"


def test_keep_flags_does_not_reuse_previous_search_selector(substitute_bot):
    editor, status, _, _ = substitute_bot
    submit(substitute_bot, "s/foo/x/r")
    editor.set_text("foo bar")
    status.cursor.set_cursor_pos(0)
    status.search.search("bar")
    submit(substitute_bot, "&&")
    assert editor.toPlainText() == "x bar"


@pytest.mark.parametrize("command", ["s/missing/x/e", "s/foo/x/n", "s/foo/foo/"])
def test_valid_no_edit_commands_become_repeat_state(substitute_bot, command):
    editor, status, _, _ = substitute_bot
    submit(substitute_bot, command)
    previous = status.last_substitute
    assert previous is not None
    editor.set_text(previous.pattern + " " + previous.pattern)
    status.cursor.set_cursor_pos(0)
    submit(substitute_bot, "s")
    assert editor.toPlainText() == previous.replacement + " " + previous.pattern


def test_invalid_command_keeps_previous_repeat_state(substitute_bot):
    editor, status, _, _ = substitute_bot
    submit(substitute_bot, "s/foo/x/g")
    previous = status.last_substitute
    submit(substitute_bot, "s/foo/z/unsupported")
    assert status.last_substitute == previous
    editor.set_text("foo foo")
    status.cursor.set_cursor_pos(0)
    submit(substitute_bot, "&&")
    assert editor.toPlainText() == "x x"


def test_repeat_state_survives_visual_mode(substitute_bot):
    editor, status, commandline, qtbot = substitute_bot
    submit(substitute_bot, "s/foo/x/g")
    editor.set_text("foo foo\nfoo foo\nfoo foo")
    status.cursor.set_cursor_pos(0)
    qtbot.keyClicks(commandline, "Vj:")
    commandline.setText(commandline.text() + "&&")
    qtbot.keyPress(commandline, Qt.Key_Return)
    assert editor.toPlainText() == "x x\nx x\nfoo foo"


def test_repeat_state_survives_file_switch(substitute_bot, vim_bot):
    editor, status, _, _ = substitute_bot
    _, stack, _, _, _ = vim_bot
    submit(substitute_bot, "s/foo/x/g")
    previous = status.last_substitute
    original_index = stack.get_stack_index()
    stack.set_stack_index(1)
    other = stack.get_current_editor()
    original_text = other.toPlainText()
    try:
        other.set_text("foo foo")
        status.cursor.set_cursor_pos(0)
        submit(substitute_bot, "&&")
        assert other.toPlainText() == "x x"
        assert status.last_substitute == previous
    finally:
        other.set_text(original_text)
        stack.set_stack_index(original_index)


def test_repeat_is_one_undo_and_redo(substitute_bot):
    editor, status, commandline, qtbot = substitute_bot
    submit(substitute_bot, "s/foo/x/g")
    editor.set_text("foo foo")
    status.cursor.set_cursor_pos(0)
    submit(substitute_bot, "&&")
    qtbot.keyClicks(commandline, "u")
    assert editor.toPlainText() == "foo foo"
    qtbot.keyPress(commandline, Qt.Key_R, modifier=Qt.ControlModifier)
    assert editor.toPlainText() == "x x"


def test_repeat_keeps_replacement_delimiter_escaping(substitute_bot):
    editor, status, _, _ = substitute_bot
    submit(substitute_bot, r"s#foo#\##g")
    editor.set_text("foo foo")
    status.cursor.set_cursor_pos(0)
    submit(substitute_bot, "&&")
    assert editor.toPlainText() == "# #"


def test_repeat_can_keep_or_clear_confirmation_flag(substitute_bot):
    editor, status, commandline, qtbot = substitute_bot
    submit(substitute_bot, "s/foo/x/gc")
    assert status.substitute_confirm is not None
    qtbot.keyClicks(commandline, "q")
    assert status.substitute_confirm is None
    previous = status.last_substitute
    submit(substitute_bot, "&&")
    assert status.substitute_confirm is not None
    assert status.last_substitute == previous
    qtbot.keyClicks(commandline, "q")
    submit(substitute_bot, "s")
    assert status.substitute_confirm is None
    assert editor.toPlainText() == "x foo\n  foo foo\nlast"
    assert status.last_substitute.flags == ""


def test_reset_clears_previous_substitute(substitute_bot):
    _, status, _, _ = substitute_bot
    submit(substitute_bot, "s/foo/x/g")
    assert status.last_substitute is not None
    reset_vim_state(status)
    assert status.last_substitute is None
