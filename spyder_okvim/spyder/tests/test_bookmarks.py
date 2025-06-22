"""Tests for the Marks."""

# Third Party Libraries
import pytest
from qtpy.QtCore import Qt

# Project Libraries
from spyder_okvim.vim import VimState


def test_bookmark_set_and_jump(vim_bot):
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\nc\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    # set bookmark 'a'
    qtbot.keyClicks(cmd_line, "ma")
    # move cursor
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(2)
    assert editor.textCursor().position() == 2
    # jump to bookmark
    qtbot.keyClicks(cmd_line, "'a")
    assert editor.textCursor().position() == 0


def test_global_bookmark_and_jump(vim_bot):
    _, stack, editor0, vim, qtbot = vim_bot
    editor0.set_text("abcd\nefgh\nijkl\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    # set bookmark 'A' (persistent)
    qtbot.keyClicks(cmd_line, "mA")
    path0 = stack.get_current_filename()

    # switch to another file
    filenames = stack.get_filenames()
    other = next(p for p in filenames if p != path0)
    stack.set_current_filename(other)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(2)

    # jump to bookmark 'A' should switch file and position
    qtbot.keyClicks(cmd_line, "'A")
    assert stack.get_current_filename() == path0
    assert editor0.textCursor().position() == 0


def test_bookmark_visual_mode(vim_bot):
    """Set and jump to bookmark while in visual mode."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("abcd\nefgh\nijkl\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "vma")
    qtbot.keyPress(cmd_line, Qt.Key_Escape)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(2)
    qtbot.keyClicks(cmd_line, "'a")
    assert editor.textCursor().position() == 0


def test_bookmark_vline_mode(vim_bot):
    """Set and jump to bookmark while in vline mode."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("abcd\nefgh\nijkl\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "Vma")
    qtbot.keyPress(cmd_line, Qt.Key_Escape)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(2)
    qtbot.keyClicks(cmd_line, "'a")
    assert editor.textCursor().position() == 0


def test_local_bookmark_not_cross_file(vim_bot):
    """Local marks should not work in other files."""
    _, stack, editor0, vim, qtbot = vim_bot
    editor0.set_text("abcd\nefgh\nijkl\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "ma")
    path0 = stack.get_current_filename()

    # switch to another file
    other = next(p for p in stack.get_filenames() if p != path0)
    stack.set_current_filename(other)
    editor_other = stack.get_current_editor()
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(2)
    pos_before = editor_other.textCursor().position()

    qtbot.keyClicks(cmd_line, "'a")
    assert editor_other.textCursor().position() == pos_before


def test_local_bookmark_not_cross_file_visual(vim_bot):
    """Local marks ignored in visual mode on other files."""
    _, stack, editor0, vim, qtbot = vim_bot
    editor0.set_text("abcd\nefgh\nijkl\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "ma")
    path0 = stack.get_current_filename()

    other = next(p for p in stack.get_filenames() if p != path0)
    stack.set_current_filename(other)
    editor_other = stack.get_current_editor()
    qtbot.keyClicks(cmd_line, "v")
    pos_before = editor_other.textCursor().position()
    qtbot.keyClicks(cmd_line, "'a")
    assert editor_other.textCursor().position() == pos_before


def test_local_bookmark_not_cross_file_vline(vim_bot):
    """Local marks ignored in vline mode on other files."""
    _, stack, editor0, vim, qtbot = vim_bot
    editor0.set_text("abcd\nefgh\nijkl\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "ma")
    path0 = stack.get_current_filename()

    other = next(p for p in stack.get_filenames() if p != path0)
    stack.set_current_filename(other)
    editor_other = stack.get_current_editor()
    qtbot.keyClicks(cmd_line, "V")
    pos_before = editor_other.textCursor().position()
    qtbot.keyClicks(cmd_line, "'a")
    assert editor_other.textCursor().position() == pos_before


def test_bookmark_removed_after_edit(vim_bot):
    """Jump should fail if mark line no longer exists."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("abcd\nefgh\nijkl\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(2)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "ma")
    editor.set_text("a\nc\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    qtbot.keyClicks(cmd_line, "'a")
    assert editor.textCursor().position() == 0


@pytest.mark.parametrize(
    "cmd_list,text_expected,cursor_pos,reg_expected",
    [
        ("y'a", "abcd\nefgh\nijkl\n", 0, "abcd\nefgh\nijkl\n"),
        ("y`a", "abcd\nefgh\nijkl\n", 2, "cd\nefgh\nijk"),
        ("d'a", "", 0, "abcd\nefgh\nijkl\n"),
        ("d`a", "abl\n", 2, "cd\nefgh\nijk"),
        ("c'a", "\n", 0, "abcd\nefgh\nijkl\n"),
        ("c`a", "abl\n", 2, "cd\nefgh\nijk"),
    ],
)
def test_mark_operations(vim_bot, cmd_list, text_expected, cursor_pos, reg_expected):
    """Test y/d/c commands with mark motions."""
    _, stack, editor, vim, qtbot = vim_bot

    # Ensure current file is the one associated with *editor*
    stack.set_current_filename(stack.get_filenames()[0])

    editor.set_text("abcd\nefgh\nijkl\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "2lma")
    qtbot.keyClicks(cmd_line, "2j")
    qtbot.keyClicks(cmd_line, cmd_list)

    reg = vim.vim_cmd.vim_status.register_dict['"']
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == reg_expected


@pytest.mark.parametrize(
    "cmd_list,text_expected,cursor_pos,reg_expected",
    [
        ("y'a", "abcd\nefgh\nijkl\n", 0, "abcd\nefgh\nijkl\n"),
        ("y`a", "abcd\nefgh\nijkl\n", 0, "abcd\nefgh\nijk"),
        ("d'a", "", 0, "abcd\nefgh\nijkl\n"),
        ("d`a", "l\n", 0, "abcd\nefgh\nijk"),
        ("c'a", "\n", 0, "abcd\nefgh\nijkl\n"),
        ("c`a", "l\n", 0, "abcd\nefgh\nijk"),
    ],
)
def test_mark_operations_after(
    vim_bot, cmd_list, text_expected, cursor_pos, reg_expected
):
    """Operations when mark is after the cursor."""
    _, stack, editor, vim, qtbot = vim_bot

    stack.set_current_filename(stack.get_filenames()[0])
    editor.set_text("abcd\nefgh\nijkl\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(12)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "ma")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    qtbot.keyClicks(cmd_line, cmd_list)

    reg = vim.vim_cmd.vim_status.register_dict['"']
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == reg_expected


@pytest.mark.parametrize(
    "cmd_list,text_expected,cursor_pos,reg_expected",
    [
        ("y'A", "abcd\nefgh\nijkl\n", 0, "abcd\nefgh\nijkl\n"),
        ("y`A", "abcd\nefgh\nijkl\n", 2, "cd\nefgh\nijk"),
        ("d'A", "", 0, "abcd\nefgh\nijkl\n"),
        ("d`A", "abl\n", 2, "cd\nefgh\nijk"),
        ("c'A", "\n", 0, "abcd\nefgh\nijkl\n"),
        ("c`A", "abl\n", 2, "cd\nefgh\nijk"),
    ],
)
def test_global_mark_operations(
    vim_bot, cmd_list, text_expected, cursor_pos, reg_expected
):
    """Global mark operations when mark is before cursor."""
    _, stack, editor, vim, qtbot = vim_bot

    stack.set_current_filename(stack.get_filenames()[0])
    editor.set_text("abcd\nefgh\nijkl\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "2lmA")
    qtbot.keyClicks(cmd_line, "2j")
    qtbot.keyClicks(cmd_line, cmd_list)

    reg = vim.vim_cmd.vim_status.register_dict['"']
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == reg_expected


@pytest.mark.parametrize(
    "cmd_list,text_expected,cursor_pos,reg_expected",
    [
        ("y'A", "abcd\nefgh\nijkl\n", 0, "abcd\nefgh\nijkl\n"),
        ("y`A", "abcd\nefgh\nijkl\n", 0, "abcd\nefgh\nijk"),
        ("d'A", "", 0, "abcd\nefgh\nijkl\n"),
        ("d`A", "l\n", 0, "abcd\nefgh\nijk"),
        ("c'A", "\n", 0, "abcd\nefgh\nijkl\n"),
        ("c`A", "l\n", 0, "abcd\nefgh\nijk"),
    ],
)
def test_global_mark_operations_after(
    vim_bot, cmd_list, text_expected, cursor_pos, reg_expected
):
    """Global mark operations when mark is after the cursor."""
    _, stack, editor, vim, qtbot = vim_bot

    stack.set_current_filename(stack.get_filenames()[0])
    editor.set_text("abcd\nefgh\nijkl\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(12)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "mA")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    qtbot.keyClicks(cmd_line, cmd_list)

    reg = vim.vim_cmd.vim_status.register_dict['"']
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == reg_expected


@pytest.mark.parametrize("cmd", ["y'A", "y`A", "d'A", "d`A", "c'A", "c`A"])
def test_global_mark_operations_removed(vim_bot, cmd):
    """Global operations should do nothing if mark was removed."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("abcd\nefgh\nijkl\n")
    # Place mark on the last line so it disappears after editing
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(10)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "mA")
    editor.set_text("b")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    reg_before = vim.vim_cmd.vim_status.register_dict['"'].content
    qtbot.keyClicks(cmd_line, cmd)
    reg_after = vim.vim_cmd.vim_status.register_dict['"'].content
    assert editor.toPlainText() == "b"
    assert editor.textCursor().position() == 0
    assert reg_before == reg_after


@pytest.mark.parametrize("cmd", ["y'A", "y`A", "d'A", "d`A", "c'A", "c`A"])
def test_global_mark_operations_cross_file(vim_bot, cmd):
    """Global mark motions ignored in other files."""
    _, stack, editor0, vim, qtbot = vim_bot

    stack.set_current_filename(stack.get_filenames()[0])
    editor0.set_text("a\nb\nc\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "mA")
    other = next(p for p in stack.get_filenames() if p != stack.get_current_filename())
    stack.set_current_filename(other)
    editor_other = stack.get_current_editor()
    editor_other.set_text("x\ny\nz\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(2)
    reg_before = vim.vim_cmd.vim_status.register_dict['"'].content
    pos_before = editor_other.textCursor().position()
    qtbot.keyClicks(cmd_line, cmd)
    reg_after = vim.vim_cmd.vim_status.register_dict['"'].content
    assert editor_other.textCursor().position() == pos_before
    assert editor_other.toPlainText() == "x\ny\nz\n"
    assert reg_before == reg_after
    vim.vim_cmd.vim_status.reset_for_test()


@pytest.mark.parametrize("cmd", ["y'a", "y`a", "d'a", "d`a", "c'a", "c`a"])
def test_mark_operations_removed(vim_bot, cmd):
    """Operations should do nothing if mark was removed."""
    _, stack, editor, vim, qtbot = vim_bot
    stack.set_current_filename(stack.get_filenames()[0])
    editor.set_text("a\nb\nc\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(4)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "ma")
    editor.set_text("b")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    reg_before = vim.vim_cmd.vim_status.register_dict['"'].content
    qtbot.keyClicks(cmd_line, cmd)
    reg_after = vim.vim_cmd.vim_status.register_dict['"'].content
    assert editor.toPlainText() == "b"
    assert editor.textCursor().position() == 0
    assert reg_before == reg_after


def test_global_bookmark_removed_after_edit(vim_bot):
    """Global mark should be cleared if its line is removed."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\nc\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "mA")
    editor.set_text("b")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    qtbot.keyClicks(cmd_line, "'A")
    assert editor.textCursor().position() == 0
    assert "A" in vim.vim_cmd.vim_status.bookmarks_global


def test_global_bookmark_overwrite(vim_bot):
    """Setting mA in another file overwrites previous global mark."""
    _, stack, editor0, vim, qtbot = vim_bot
    stack.set_current_filename(stack.get_filenames()[0])
    editor0 = stack.get_current_editor()
    editor0.set_text("abcd\nefgh\nijkl\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "mA")
    other = next(p for p in stack.get_filenames() if p != stack.get_current_filename())
    stack.set_current_filename(other)
    editor_other = stack.get_current_editor()
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(2)
    qtbot.keyClicks(cmd_line, "mA")
    stack.set_current_filename(stack.get_filenames()[0])
    qtbot.keyClicks(cmd_line, "'A")
    assert stack.get_current_filename() == other
    stack.set_current_filename(stack.get_filenames()[0])


@pytest.mark.parametrize("cmd,pos_expected", [("'a", 0), ("`a", 2)])
def test_jump_mark_visual_before_after(vim_bot, cmd, pos_expected):
    """Jump to mark from visual mode with mark before and after cursor."""
    _, stack, editor, vim, qtbot = vim_bot
    stack.set_current_filename(stack.get_filenames()[0])
    editor.set_text("abcd\nefgh\nijkl\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "2lma")
    qtbot.keyClicks(cmd_line, "2j")
    qtbot.keyClicks(cmd_line, "v")
    qtbot.keyClicks(cmd_line, cmd)
    assert vim.vim_cmd.vim_status.vim_state == VimState.VISUAL
    assert editor.textCursor().position() == pos_expected


@pytest.mark.parametrize("cmd", ["'a", "`a"])
def test_jump_mark_visual_removed(vim_bot, cmd):
    """Jump should do nothing if mark line was removed."""
    _, stack, editor, vim, qtbot = vim_bot
    stack.set_current_filename(stack.get_filenames()[0])
    editor.set_text("abcd\nefgh\nijkl\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(10)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "ma")
    editor.set_text("x")
    qtbot.keyClicks(cmd_line, "v")
    qtbot.keyClicks(cmd_line, cmd)
    assert editor.textCursor().position() == 0
    assert vim.vim_cmd.vim_status.vim_state == VimState.VISUAL
    assert vim.vim_cmd.vim_status.vim_state == VimState.VISUAL


@pytest.mark.parametrize("cmd,pos_expected", [("'A", 0), ("`A", 2)])
def test_jump_global_mark_visual(vim_bot, cmd, pos_expected):
    """Jump to global mark from visual mode."""
    _, stack, editor, vim, qtbot = vim_bot
    stack.set_current_filename(stack.get_filenames()[0])
    editor.set_text("abcd\nefgh\nijkl\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "2lmA")
    qtbot.keyClicks(cmd_line, "2j")
    qtbot.keyClicks(cmd_line, "v")
    qtbot.keyClicks(cmd_line, cmd)
    assert stack.get_current_filename() == stack.get_filenames()[0]
    assert editor.textCursor().position() == pos_expected
    assert vim.vim_cmd.vim_status.vim_state == VimState.VISUAL


@pytest.mark.parametrize("cmd,pos_expected", [("'A", 0), ("`A", 2)])
def test_jump_global_mark_visual_cross_file(vim_bot, cmd, pos_expected):
    """Global mark jump from another file in visual mode."""
    _, stack, editor0, vim, qtbot = vim_bot
    stack.set_current_filename(stack.get_filenames()[0])
    editor0.set_text("abcd\nefgh\nijkl\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "2lmA")
    other = next(p for p in stack.get_filenames() if p != stack.get_current_filename())
    stack.set_current_filename(other)
    editor_other = stack.get_current_editor()
    qtbot.keyClicks(cmd_line, "v")
    qtbot.keyClicks(cmd_line, cmd)
    assert stack.get_current_filename() == stack.get_filenames()[0]
    assert editor0.textCursor().position() == pos_expected
    assert vim.vim_cmd.vim_status.vim_state == VimState.NORMAL


@pytest.mark.parametrize("cmd", ["'A", "`A"])
def test_jump_global_mark_visual_removed(vim_bot, cmd):
    """Global mark jump does nothing if its line was removed."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("abcd\nefgh\nijkl\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(10)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "mA")
    editor.set_text("x")
    qtbot.keyClicks(cmd_line, "v")
    qtbot.keyClicks(cmd_line, cmd)
    assert editor.textCursor().position() == 0
