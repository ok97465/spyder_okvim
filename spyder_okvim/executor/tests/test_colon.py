# -*- coding: utf-8 -*-
"""Tests for :mod:`spyder_okvim.executor.executor_colon`."""

# Third Party Libraries
import pytest
from qtpy.QtCore import Qt


@pytest.mark.parametrize(
    "text, cmd_list, cmd_line_expected",
    [
        ("", [":", "k", "k"], ":kk"),
        ("", [":", "k", "k", Qt.Key_Escape], ""),
    ],
)
def test_colon_cmd(vim_bot, text, cmd_list, cmd_line_expected):
    """Test colon command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert cmd_line.text() == cmd_line_expected


@pytest.mark.parametrize(
    "text, cmd_list",
    [
        ("", [":", Qt.Key_Return]),
        ("", [":", Qt.Key_Left, "d", Qt.Key_Enter]),
    ],
)
def test_colon_corner_case_cmd(vim_bot, text, cmd_list):
    """Test colon command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert vim.vim_cmd.vim_status.sub_mode is None


def test_colon_w_command(vim_bot):
    """Test :w."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, ":")
    qtbot.keyClicks(cmd_line, "w")
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    main.editor.save_action.trigger.assert_called_once_with()
    main.editor.save_action.trigger.reset_mock()


def test_colon_q_command(vim_bot):
    """Test :q."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, ":")
    qtbot.keyClicks(cmd_line, "q")
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    main.editor.close_file.assert_called_once_with()
    main.editor.close_file.reset_mock()


def test_colon_q_command_without_close_file(vim_bot):
    """Test :q when close_file API is missing."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    orig_close_file = main.editor.close_file
    delattr(main.editor, "close_file")
    with pytest.raises(AttributeError):
        vim.vim_cmd.executor_normal_cmd.executor_colon.q()
    main.editor.close_file = orig_close_file


def test_colon_qexclamation_command(vim_bot):
    """Test :q!."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, ":")
    qtbot.keyClicks(cmd_line, "q")
    qtbot.keyClicks(cmd_line, "!")
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    main.editor.close_file.assert_called_once_with()
    main.editor.close_file.reset_mock()


def test_colon_wq_command(vim_bot):
    """Test :wq."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, ":")
    qtbot.keyClicks(cmd_line, "w")
    qtbot.keyClicks(cmd_line, "q")
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    main.editor.save_action.trigger.assert_called_once_with()
    main.editor.close_file.assert_called_once_with()
    main.editor.save_action.trigger.reset_mock()
    main.editor.close_file.reset_mock()


def test_colon_n_command(vim_bot):
    """Test :n."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, ":")
    qtbot.keyClicks(cmd_line, "n")
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    main.editor.new_action.trigger.assert_called_once_with()


def test_colon_backspace_command(vim_bot):
    """Test backspace in ex cmd."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, ":")
    qtbot.keyClicks(cmd_line, "n")
    qtbot.keyPress(cmd_line, Qt.Key_Backspace)

    assert cmd_line.text() == ":"
    assert vim.vim_cmd.vim_status.sub_mode is not None

    qtbot.keyPress(cmd_line, Qt.Key_Backspace)

    assert cmd_line.text() == ""
    assert vim.vim_cmd.vim_status.sub_mode is None

def test_colon_marks_command(vim_bot, monkeypatch):
    """Test :marks opens dialog and jumps to the selected mark."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\nc\n")
    vs = vim.vim_cmd.vim_status
    vs.cursor.set_cursor_pos(2)
    vs.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "ma")
    vs.cursor.set_cursor_pos(0)

    from spyder_okvim.utils import mark_dialog

    monkeypatch.setattr(mark_dialog.MarkListDialog, "exec_", lambda self: None)
    monkeypatch.setattr(mark_dialog.MarkListDialog, "get_selected_mark", lambda self: "a")

    qtbot.keyClicks(cmd_line, ":")
    qtbot.keyClicks(cmd_line, "marks")
    qtbot.keyPress(cmd_line, Qt.Key_Return)

    assert editor.textCursor().position() == 2
