# -*- coding: utf-8 -*-
"""Tests for :mod:`spyder_okvim.executor.executor_colon`."""

# Standard Libraries
from unittest.mock import Mock

# Third Party Libraries
import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDialog

# Project Libraries
from tests.qt_support import reset_vim_state


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
    reset_vim_state(vim.vim_cmd.vim_status)

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
    reset_vim_state(vim.vim_cmd.vim_status)

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
    main.editor.save.assert_called_once_with()
    main.editor.save.reset_mock()


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


def test_colon_qexclamation_command(vim_bot, monkeypatch):
    """Test :q!."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    close = Mock()
    monkeypatch.setattr(editor_stack, "close_file", close)
    monkeypatch.setattr(editor_stack.autosave, "remove_autosave_file", Mock())
    monkeypatch.setattr(
        main.editor, "can_close_file", Mock(return_value=True), raising=False
    )
    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, ":")
    qtbot.keyClicks(cmd_line, "q")
    qtbot.keyClicks(cmd_line, "!")
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    close.assert_called_once_with(force=True)
    main.editor.close_file.assert_not_called()


def test_colon_wq_command(vim_bot, monkeypatch):
    """Test :wq."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    monkeypatch.setattr(main.editor, "save", Mock(return_value=True))
    monkeypatch.setattr(main.editor, "close_file", Mock())
    finfo = editor_stack.get_current_finfo()
    monkeypatch.setattr(finfo, "newly_created", False)
    monkeypatch.setattr(finfo.editor.document(), "isModified", lambda: False)
    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, ":")
    qtbot.keyClicks(cmd_line, "w")
    qtbot.keyClicks(cmd_line, "q")
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    main.editor.save.assert_called_once_with()
    main.editor.close_file.assert_called_once_with()
    main.editor.save.reset_mock()
    main.editor.close_file.reset_mock()


def test_colon_n_command(vim_bot):
    """Test :n."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, ":")
    qtbot.keyClicks(cmd_line, "n")
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    main.editor.new.assert_called_once_with()


@pytest.mark.parametrize("command", ["vs", "vsp", "vsplit"])
def test_colon_vsplit_command(vim_bot, command):
    """Each alias splits the active stack from left to right."""
    _, stack, _, vim, qtbot = vim_bot
    status = vim.vim_cmd.vim_status
    commandline = vim.vim_cmd.commandline
    commandline.setFocus()
    commandline.esc_pressed()

    with qtbot.waitSignal(stack.sig_split_horizontally):
        qtbot.keyClicks(commandline, ":" + command)
        qtbot.keyPress(commandline, Qt.Key_Return)

    assert status.is_normal()
    assert status.sub_mode is None
    assert commandline.text() == ""
    assert commandline.hasFocus()


def test_colon_vsplit_completion(vim_bot):
    """The split aliases participate in the existing command completer."""
    _, _, _, vim, qtbot = vim_bot
    commandline = vim.vim_cmd.commandline
    commandline.setFocus()
    commandline.esc_pressed()
    qtbot.keyClicks(commandline, ":v")

    for expected in (":vs", ":vsp", ":vsplit"):
        qtbot.keyPress(commandline, Qt.Key_Tab)
        assert commandline.text() == expected
    commandline.esc_pressed()


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


def test_colon_marks_command(vim_bot):
    """A mark is selected in the shared modeless picker before navigation."""
    _, _, editor, vim, qtbot = vim_bot
    widget = vim.vim_cmd
    status = widget.vim_status
    reset_vim_state(status)
    editor.set_text("a\nb\nc\n")
    status.cursor.set_cursor_pos(2)
    status.bookmark_manager.set_bookmark("a")
    status.cursor.set_cursor_pos(0)
    qtbot.keyClicks(widget.commandline, ":marks")
    qtbot.keyClick(widget.commandline, Qt.Key_Return)
    picker = widget.picker
    qtbot.waitUntil(lambda: picker.result_token == picker._search_token())
    picker.dialog.prompt.setText("a")
    qtbot.waitUntil(lambda: picker.result_token == picker._search_token())
    assert editor.textCursor().position() == 0
    qtbot.keyClick(picker.dialog.prompt, Qt.Key_Return)
    qtbot.waitUntil(lambda: picker.phase == "closed")
    assert editor.textCursor().position() == 2


def test_colon_marks_escape_focus(vim_bot):
    _, _, editor, vim, qtbot = vim_bot
    widget = vim.vim_cmd
    reset_vim_state(widget.vim_status)
    before = (editor.toPlainText(), editor.textCursor().position())
    qtbot.keyClicks(widget.commandline, ":marks")
    qtbot.keyClick(widget.commandline, Qt.Key_Return)
    qtbot.keyClick(widget.picker.dialog.prompt, Qt.Key_Escape)
    qtbot.waitUntil(lambda: widget.picker.phase == "closed")
    assert (editor.toPlainText(), editor.textCursor().position()) == before
    assert widget.commandline.hasFocus()


def test_colon_jumps_dialog_navigation(vim_bot):
    _, stack, _, vim, qtbot = vim_bot
    widget = vim.vim_cmd
    status = widget.vim_status
    reset_vim_state(status)
    original = stack.get_current_filename()
    filenames = stack.get_filenames()[:3]
    status.jump_list.jumps.clear()
    status.jump_list.index = 0
    for filename in filenames:
        status.jump_list.push(filename, 0)
    stack.set_current_filename(filenames[-1])
    try:
        qtbot.keyClicks(widget.commandline, ":jumps")
        qtbot.keyClick(widget.commandline, Qt.Key_Return)
        picker = widget.picker
        qtbot.waitUntil(lambda: picker.result_token == picker._search_token())
        qtbot.keyClick(picker.dialog.prompt, Qt.Key_O, Qt.ControlModifier)
        assert stack.get_current_filename() == filenames[-2]
        assert picker.phase == "active"
        qtbot.keyClick(picker.dialog.prompt, Qt.Key_I, Qt.ControlModifier)
        assert stack.get_current_filename() == filenames[-1]
        picker.dialog.reject()
        qtbot.waitUntil(lambda: picker.phase == "closed")
    finally:
        widget.picker.cancel()
        stack.set_current_filename(original)


def test_colon_jumps_selected_row_opens_only_its_location(vim_bot):
    _, stack, _, vim, qtbot = vim_bot
    widget = vim.vim_cmd
    status = widget.vim_status
    reset_vim_state(status)
    original = stack.get_current_filename()
    filenames = stack.get_filenames()
    status.jump_list.jumps.clear()
    status.jump_list.index = 0
    for filename in filenames:
        status.jump_list.push(filename, 0)
    stack.set_current_filename(filenames[-1])
    try:
        qtbot.keyClicks(widget.commandline, ":jumps")
        qtbot.keyClick(widget.commandline, Qt.Key_Return)
        picker = widget.picker
        qtbot.waitUntil(lambda: picker.result_token == picker._search_token())
        picker.dialog.select_id(f"{picker.host.history_version}:0")
        assert stack.get_current_filename() == filenames[-1]
        qtbot.keyClick(picker.dialog.prompt, Qt.Key_Return)
        qtbot.waitUntil(lambda: picker.phase == "closed")
        assert stack.get_current_filename() == filenames[0]
        assert status.jump_list.index == 1
    finally:
        widget.picker.cancel()
        stack.set_current_filename(original)
