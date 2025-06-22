# -*- coding: utf-8 -*-
"""Integration style tests using vim commands."""

from qtpy.QtCore import Qt, QEvent
from qtpy.QtGui import QKeyEvent

from spyder_okvim.utils.file_search import FileSearchDialog


def test_indent_unindent_commands(vim_bot):
    """Indent two lines and then unindent them using commands."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\nc")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "V")
    qtbot.keyClicks(cmd_line, "j")
    qtbot.keyClicks(cmd_line, ">")
    assert editor.toPlainText() == "    a\n    b\nc"
    qtbot.keyClicks(cmd_line, "V")
    qtbot.keyClicks(cmd_line, "j")
    qtbot.keyClicks(cmd_line, "<")
    assert editor.toPlainText() == "a\nb\nc"
    assert cmd_line.text() == ""


def test_surround_add_delete(vim_bot):
    """Add and delete a surrounding using Vim commands."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("abde")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "l")
    qtbot.keyClicks(cmd_line, "v")
    qtbot.keyClicks(cmd_line, "lS")
    qtbot.keyClicks(cmd_line, ")")
    assert editor.toPlainText() == "a(bd)e"

    qtbot.keyClicks(cmd_line, "ds")
    qtbot.keyClicks(cmd_line, ")")
    assert editor.toPlainText() == "abde"
    assert cmd_line.text() == ""


def test_file_search_via_command(vim_bot, tmpdir, monkeypatch):
    """Open file search with a command and select a file."""
    _, _, _, vim, qtbot = vim_bot

    folder = tmpdir.mkdir("proj")
    fn = folder.join("abc.py")
    fn.write("content")

    def fake_exec(self):
        self.edit.setText("ab")
        self.update_list()
        self.enter()

    monkeypatch.setattr(FileSearchDialog, "exec_", fake_exec)
    monkeypatch.setattr(vim.main.projects, "get_active_project_path", lambda: str(folder))

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_P, Qt.ControlModifier)
    vim.vim_cmd.commandline.keyPressEvent(event)

    vim.main.open_file.assert_called_with(str(fn))


def test_join_lines_and_replace(vim_bot):
    """Join lines with ``J`` and replace characters with ``r``."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\nc")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "J")
    assert editor.toPlainText().startswith("a b")

    qtbot.keyClicks(cmd_line, "r")
    qtbot.keyClicks(cmd_line, "x")
    assert editor.toPlainText().startswith("ax")
    assert cmd_line.text() == ""
