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

