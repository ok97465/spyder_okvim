import pytest
from qtpy.QtCore import Qt


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
    editor0.set_text("a\nb\nc\n")
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
    editor.set_text("a\nb\nc\n")
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
    editor.set_text("a\nb\nc\n")
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
    editor0.set_text("a\nb\nc\n")
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
    editor0.set_text("a\nb\nc\n")
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
    editor0.set_text("a\nb\nc\n")
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
    editor.set_text("a\nb\nc\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(2)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "ma")
    editor.set_text("a\nc\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    qtbot.keyClicks(cmd_line, "'a")
    assert editor.textCursor().position() == 0


@pytest.mark.parametrize(
    "cmd,text_expected,cursor_pos,reg_expected",
    [
        ("y'a", "a\nb\nc\n", 0, "a\nb\nc\n"),
        ("y`a", "a\nb\nc\n", 0, "a\nb\nc"),
        ("d'a", "", 0, "a\nb\nc\n"),
        ("d`a", "\n", 0, "a\nb\nc"),
        ("c'a", "\n", 0, "a\nb\nc\n"),
        ("c`a", "\n", 0, "a\nb\nc"),
    ],
)
def test_mark_operations(vim_bot, cmd, text_expected, cursor_pos, reg_expected):
    """Test y/d/c commands with mark motions."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\nc\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "ma")
    qtbot.keyClicks(cmd_line, "2j")
    qtbot.keyClicks(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict['"']
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == reg_expected


@pytest.mark.parametrize("cmd", ["y'a", "y`a", "d'a", "d`a", "c'a", "c`a"])
def test_mark_operations_removed(vim_bot, cmd):
    """Operations should do nothing if mark was removed."""
    _, _, editor, vim, qtbot = vim_bot
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
    assert 'A' in vim.vim_cmd.vim_status.bookmarks_global


def test_global_bookmark_overwrite(vim_bot):
    """Setting mA in another file overwrites previous global mark."""
    _, stack, editor0, vim, qtbot = vim_bot
    editor0.set_text("a\nb\nc\n")
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
    assert editor_other.textCursor().position() == 2
