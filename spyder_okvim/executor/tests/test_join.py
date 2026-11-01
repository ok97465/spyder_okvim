"""gJ preserves whitespace and the count, Visual shape and undo boundaries."""

# Third Party Libraries
import pytest
from qtpy.QtCore import Qt

# Project Libraries
from spyder_okvim.vim.state import VimState
from tests.qt_support import reset_vim_state


@pytest.fixture
def join_bot(vim_bot):
    """Keep the editor and command state local to each join scenario."""
    _, stack, _, vim, qtbot = vim_bot
    previous_index = stack.get_stack_index()
    line = vim.vim_cmd.commandline
    status = vim.vim_cmd.vim_status
    line.esc_pressed()
    status.disconnect_from_editor()
    stack.set_stack_index(0)
    reset_vim_state(status)
    editor = stack.get_current_editor()
    original = editor.toPlainText()
    line.clear()
    line.setFocus()
    try:
        yield editor, status, line, qtbot
    finally:
        line.esc_pressed()
        status.disconnect_from_editor()
        reset_vim_state(status)
        editor.set_text(original)
        stack.set_stack_index(previous_index)


def prepare(join_bot, text):
    """Set a fresh document with the cursor at its first character."""
    editor, status, line, bot = join_bot
    editor.set_text(text)
    status.cursor.set_cursor_pos(0)
    return editor, status, line, bot


@pytest.mark.parametrize(
    "text, command, expected, position",
    [
        ("a \n  b\nc", "gJ", "a   b\nc", 2),
        ("a \n  b\nc", "2gJ", "a   b\nc", 2),
        ("a \n  b\nc\nd", "3gJ", "a   bc\nd", 5),
        ("a \n  b\nc\nd", "99gJ", "a   bcd", 6),
        ("a\n\nb", "3gJ", "ab", 1),
        ("a\n \t\nb", "3gJ", "a \tb", 3),
        ("a \n\t b", "gJ", "a \t b", 2),
        ("😀\n  가", "gJ", "😀  가", 2),
        ("a\n", "gJ", "a", 0),
        ("", "gJ", "", 0),
        ("single", "gJ", "single", 0),
    ],
)
def test_gj_preserves_whitespace_and_count(join_bot, text, command, expected, position):
    """Only block separators disappear, and the cursor reaches the last seam."""
    editor, status, line, bot = prepare(join_bot, text)

    bot.keyClicks(line, command)

    assert editor.toPlainText() == expected
    assert editor.textCursor().position() == position
    if editor.textCursor().block().text():
        assert editor.textCursor().block().layout().isValidCursorPosition(position)
    assert status.vim_state == VimState.NORMAL
    assert line.text() == ""


@pytest.mark.parametrize("selection", ["v2j", "V2j", "2jvk", "2jVk"])
def test_visual_gj_joins_selected_rows(join_bot, selection):
    """Both Visual kinds use the selected rows, including reverse selections."""
    original = "a \n  b\nc\nd"
    editor, status, line, bot = prepare(join_bot, original)
    expected = "a   bc\nd" if selection.startswith(("v", "V")) else "a \n  bc\nd"

    bot.keyClicks(line, selection + "gJ")

    assert editor.toPlainText() == expected
    assert status.vim_state == VimState.NORMAL
    assert status.get_pos_start_in_selection() is None
    assert line.text() == ""
    bot.keyClicks(line, "u")
    assert editor.toPlainText() == original


@pytest.mark.parametrize("command", ["3gJ", "v2jgJ", "V2jgJ"])
def test_gj_dot_repeat_and_independent_undo(join_bot, command):
    """Dot retains the original count or Visual shape, and each join is one edit."""
    original = "a\n b\nc\n d\ne\n f\nz"
    editor, status, line, bot = prepare(join_bot, original)
    bot.keyClicks(line, command)
    after_first = editor.toPlainText()
    assert after_first == "a bc\n d\ne\n f\nz"

    bot.keyClicks(line, ".")

    assert editor.toPlainText() == "a bc de\n f\nz"
    bot.keyClicks(line, "u")
    assert editor.toPlainText() == after_first
    bot.keyClicks(line, "u")
    assert editor.toPlainText() == original
    bot.keyPress(line, Qt.Key_R, Qt.ControlModifier)
    assert editor.toPlainText() == after_first
    assert status.vim_state == VimState.NORMAL
