"""Regression tests for register selection when replaying the last change."""

# Third Party Libraries
import pytest

# Project Libraries
from spyder_okvim.vim.state import VimState


def prepare_editor(vim_bot, text):
    """Start each case with independent command and register state."""
    _, _, editor, vim, qtbot = vim_bot
    cmd_line = vim.vim_cmd.commandline
    cmd_line.esc_pressed()
    status = vim.vim_cmd.vim_status
    status.disconnect_from_editor()
    status.reset_for_test()
    editor.set_text(text)
    status.cursor.set_cursor_pos(0)
    cmd_line.clear()
    cmd_line.setFocus()
    status.set_register('"', "unnamed", VimState.NORMAL)
    return editor, status, cmd_line, qtbot


@pytest.mark.parametrize(
    "command, initial_count, repeat, pasted_count",
    [
        ("p", "", ".", 2),
        ("P", "", ".", 2),
        ("p", "", "3.", 4),
        ("P", "", "3.", 4),
        ("p", "2", ".", 4),
        ("P", "2", "3.", 5),
    ],
)
def test_dot_preserves_normal_paste_register(
    vim_bot, command, initial_count, repeat, pasted_count
):
    """Plain/count-prefixed dot reuses the register and chooses the right count."""
    editor, status, cmd_line, qtbot = prepare_editor(vim_bot, "x")
    status.set_register("a", "A", VimState.NORMAL)

    qtbot.keyClicks(cmd_line, f'"a{initial_count}{command}')
    qtbot.keyClicks(cmd_line, repeat)

    content = "A" * pasted_count
    expected = "x" + content if command == "p" else content + "x"
    assert editor.toPlainText() == expected
    assert status.register_dict['"'].content == "unnamed"
    assert cmd_line.text() == ""
    assert status.is_normal()


@pytest.mark.parametrize(
    "command, repeat, expected",
    [
        ("p", ".", "x\nA\nA\ny"),
        ("P", "2.", "A\nA\nA\nx\ny"),
    ],
)
def test_dot_preserves_linewise_paste_register(vim_bot, command, repeat, expected):
    """Register selection also preserves linewise paste placement."""
    editor, status, cmd_line, qtbot = prepare_editor(vim_bot, "x\ny")
    status.set_register("a", "A\n", VimState.VLINE)

    qtbot.keyClicks(cmd_line, f'"a{command}')
    qtbot.keyClicks(cmd_line, repeat)

    assert editor.toPlainText() == expected
    assert status.register_dict['"'].content == "unnamed"
    assert cmd_line.text() == ""
    assert status.is_normal()


@pytest.mark.parametrize("register", ["a", "0"])
def test_dot_preserves_visual_paste_register(vim_bot, register):
    """Rebuilding a Visual selection must retain the editing register."""
    editor, status, cmd_line, qtbot = prepare_editor(vim_bot, "abcd\nefgh")
    status.set_register('"', "U", VimState.NORMAL)
    status.set_register("a", "XY", VimState.NORMAL)
    status.set_register("0", "XY", VimState.NORMAL)

    qtbot.keyClicks(cmd_line, f'vl"{register}p')
    qtbot.keyClicks(cmd_line, "j0.")

    assert editor.toPlainText() == "XYcd\nXYgh"
    assert cmd_line.text() == ""
    assert status.is_normal()


def test_dot_preserves_multiline_visual_paste_register(vim_bot):
    """The vertical and column motions in a repeated selection retain its register."""
    editor, status, cmd_line, qtbot = prepare_editor(vim_bot, "ab\ncd\nef\ngh\nij")
    status.set_register("a", "Z", VimState.NORMAL)

    qtbot.keyClicks(cmd_line, 'vj"ap')
    qtbot.keyClicks(cmd_line, "j0.")

    assert editor.toPlainText() == "Zd\nZh\nij"
    assert status.register_dict['"'].content == "unnamed"
    assert cmd_line.text() == ""
    assert status.is_normal()


def test_dot_preserves_vline_paste_register(vim_bot):
    """Rebuilding a line selection retains the named paste register."""
    editor, status, cmd_line, qtbot = prepare_editor(vim_bot, "a\nb\nc\nd\ne")
    status.set_register('"', "U\nW\n", VimState.VLINE)
    status.set_register("a", "X\nY\n", VimState.VLINE)

    qtbot.keyClicks(cmd_line, 'Vj"ap')
    qtbot.keyClicks(cmd_line, "2j.")

    assert editor.toPlainText() == "X\nY\nX\nY\ne"
    assert cmd_line.text() == ""
    assert status.is_normal()


@pytest.mark.parametrize(
    "text, command, repeat, expected, deleted, register_type",
    [
        ("abcdef", '"ax', "2.", "def", "bc", VimState.NORMAL),
        ("abcdef", 'vl"ad', ".", "ef", "cd", VimState.NORMAL),
        ("a\nb\nc\nd\ne", 'Vj"ad', ".", "e", "c\nd\n", VimState.VLINE),
    ],
)
def test_dot_preserves_delete_register(
    vim_bot, text, command, repeat, expected, deleted, register_type
):
    """Repeated deletion writes to the originally selected register."""
    editor, status, cmd_line, qtbot = prepare_editor(vim_bot, text)

    qtbot.keyClicks(cmd_line, command)
    qtbot.keyClicks(cmd_line, repeat)

    assert editor.toPlainText() == expected
    assert status.register_dict["a"].content == deleted
    assert status.register_dict["a"].type == register_type
    assert status.register_dict['"'].content == "unnamed"
    assert cmd_line.text() == ""
    assert status.is_normal()


def test_dot_without_register_prefix_uses_current_unnamed_register(vim_bot):
    """An ordinary paste still replays against the current default register."""
    editor, status, cmd_line, qtbot = prepare_editor(vim_bot, "x")
    status.set_register('"', "A", VimState.NORMAL)
    status.set_register("a", "named", VimState.NORMAL)

    qtbot.keyClicks(cmd_line, "p")
    status.set_register('"', "B", VimState.NORMAL)
    qtbot.keyClicks(cmd_line, ".")

    assert editor.toPlainText() == "xAB"
    assert cmd_line.text() == ""
    assert status.is_normal()
