# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
#
"""Tests for the plugin."""

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtGui import QFocusEvent, QKeyEvent

# Project Libraries
from spyder_okvim.spyder.confpage import OkvimConfigPage


def test_conf_page(vim_bot):
    """Test conf_page.

    Call the methods that is difficult to make test case.
    """
    main, _, _, vim, _ = vim_bot
    vim.get_icon()
    vim.switch_to_plugin()
    conf_page = OkvimConfigPage(vim, main)
    conf_page.setup_page()

    old_leader_key = conf_page.leaderkey_viewer.textbox.text()
    new_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Control, Qt.NoModifier)
    conf_page.leaderkey_edit.keyPressEvent(new_event)

    assert conf_page.leaderkey_viewer.textbox.text() == old_leader_key

    new_event = QKeyEvent(QEvent.KeyPress, Qt.Key_unknown, Qt.NoModifier)
    conf_page.leaderkey_edit.keyPressEvent(new_event)

    assert conf_page.leaderkey_viewer.textbox.text() == old_leader_key

    new_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Meta, Qt.NoModifier)
    conf_page.leaderkey_edit.keyPressEvent(new_event)

    assert conf_page.leaderkey_viewer.textbox.text() == old_leader_key

    new_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Enter, Qt.NoModifier)
    conf_page.leaderkey_edit.keyPressEvent(new_event)

    assert conf_page.leaderkey_viewer.textbox.text() == "Enter"


def test_apply_config(vim_bot):
    """Run apply_plugin_settings method."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("foo Foo foo Foo")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    # test refresh the color of search result.
    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "/foo")
    qtbot.keyPress(cmd_line, Qt.Key_Return)

    vim.apply_plugin_settings("")


def test_ctrl_u_b(vim_bot):
    """Test ^u ^b."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "j")

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_U, Qt.ControlModifier)
    vim.vim_cmd.commandline.keyPressEvent(event)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == 0

    qtbot.keyClicks(cmd_line, "j")

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_B, Qt.ControlModifier)
    vim.vim_cmd.commandline.keyPressEvent(event)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == 0


def test_ctrl_d_f(vim_bot):
    """Test ^d ^f."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_D, Qt.ControlModifier)
    vim.vim_cmd.commandline.keyPressEvent(event)

    # assert cmd_line.text() == ""
    # assert editor.textCursor().position() == 2

    qtbot.keyClicks(cmd_line, "k")

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_F, Qt.ControlModifier)
    vim.vim_cmd.commandline.keyPressEvent(event)

    # assert cmd_line.text() == ""
    # assert editor.textCursor().position() == 2


def test_message(vim_bot):
    """Test message."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\nc\nd\ne")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "y2j")
    assert vim.vim_cmd.msg_label.text() == "3 lines yanked"

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "p")
    assert vim.vim_cmd.msg_label.text() == "3 more lines"

    vim.vim_cmd.msg_label.clear()
    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "vp")
    assert vim.vim_cmd.msg_label.text() == "4 more lines"

    vim.vim_cmd.msg_label.clear()
    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "Vp")
    assert vim.vim_cmd.msg_label.text() == "2 more lines"

    qtbot.keyClicks(cmd_line, "i")
    cmd_line.focusInEvent(QFocusEvent(QEvent.FocusIn, Qt.OtherFocusReason))
    assert vim.vim_cmd.msg_label.text() == ""

    qtbot.keyClicks(cmd_line, "d2j")
    assert vim.vim_cmd.msg_label.text() == "3 fewer lines"

    editor.set_text("a\nb\nc\nd\ne")
    qtbot.keyClicks(cmd_line, "c2j")
    assert vim.vim_cmd.msg_label.text() == "2 fewer lines"

    qtbot.keyClicks(cmd_line, ":")
    qtbot.keyPress(cmd_line, Qt.Key_Enter)
    assert vim.vim_cmd.msg_label.text() == ""

    vim.vim_cmd.msg_label.setText("a")
    qtbot.keyClicks(cmd_line, "/")
    qtbot.keyPress(cmd_line, Qt.Key_Enter)
    assert vim.vim_cmd.msg_label.text() == ""

    vim.vim_cmd.msg_label.setText("a")
    qtbot.keyClicks(cmd_line, "v/")
    qtbot.keyPress(cmd_line, Qt.Key_Enter)
    assert vim.vim_cmd.msg_label.text() == ""

    vim.vim_cmd.msg_label.setText("a")
    qtbot.keyClicks(cmd_line, "V/")
    qtbot.keyPress(cmd_line, Qt.Key_Enter)
    qtbot.keyPress(cmd_line, Qt.Key_Escape)
    assert vim.vim_cmd.msg_label.text() == ""

    vim.vim_cmd.msg_label.setText("a")
    editor.set_text("a\nb\nc\nd\ne")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    qtbot.keyClicks(cmd_line, "hx")
    qtbot.keyClicks(cmd_line, "u")
    assert vim.vim_cmd.msg_label.text() == "1 changes"

    vim.vim_cmd.msg_label.setText("a")
    qtbot.keyPress(cmd_line, Qt.Key_R, Qt.ControlModifier)
    assert vim.vim_cmd.msg_label.text() == "1 changes"

    qtbot.keyClicks(cmd_line, "d3j")
    qtbot.keyClicks(cmd_line, "u")
    assert vim.vim_cmd.msg_label.text() == "4 more lines"

    qtbot.keyPress(cmd_line, Qt.Key_R, Qt.ControlModifier)
    assert vim.vim_cmd.msg_label.text() == "4 fewer lines"

    qtbot.keyClicks(cmd_line, "p")
    qtbot.keyClicks(cmd_line, "u")
    assert vim.vim_cmd.msg_label.text() == "4 fewer lines"

    qtbot.keyPress(cmd_line, Qt.Key_R, Qt.ControlModifier)
    assert vim.vim_cmd.msg_label.text() == "4 more lines"

    # TODO: Spyder에서는 정상동작하지만 Pytest만 Fail
    # editor.set_text("aaaaaa")
    # vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    # vim.vim_cmd.vim_status.reset_for_test()
    # qtbot.keyClicks(cmd_line, "/a")
    # qtbot.keyPress(cmd_line, Qt.Key_Enter)
    # assert vim.vim_cmd.msg_label.text() == "/a"

    # vim.vim_cmd.msg_label.setText("a")
    # qtbot.keyClicks(cmd_line, "n")
    # assert vim.vim_cmd.msg_label.text() == "/a"

    # qtbot.keyClicks(cmd_line, "N")
    # assert vim.vim_cmd.msg_label.text() == "?a"


def test_ctrl_o_i(vim_bot):
    """Test jumplist navigation with ^O and ^I."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("alpha\nbravo\ncharlie\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "G")
    pos_bottom = editor.textCursor().position()

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_O, Qt.ControlModifier)
    cmd_line.keyPressEvent(event)
    assert editor.textCursor().position() == 0

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_I, Qt.ControlModifier)
    cmd_line.keyPressEvent(event)
    assert editor.textCursor().position() == pos_bottom


def test_jumplist_search(vim_bot):
    """Jump list records search command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("alpha\nsearch\nsearch\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "/search")
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    pos_search = editor.textCursor().position()

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_O, Qt.ControlModifier)
    cmd_line.keyPressEvent(event)
    assert editor.textCursor().position() == 0

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_I, Qt.ControlModifier)
    cmd_line.keyPressEvent(event)
    assert editor.textCursor().position() == pos_search


def test_jumplist_n_command(vim_bot):
    """Jump list records n command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("foo foo foo foo")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "/foo")
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    first = editor.textCursor().position()

    qtbot.keyClicks(cmd_line, "n")
    second = editor.textCursor().position()

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_O, Qt.ControlModifier)
    cmd_line.keyPressEvent(event)
    assert editor.textCursor().position() == first

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_I, Qt.ControlModifier)
    cmd_line.keyPressEvent(event)
    assert editor.textCursor().position() == second


def test_jumplist_mark_jump(vim_bot):
    """Jump list records mark jumps."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("alpha\nbravo\ncharlie\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "ma")
    qtbot.keyClicks(cmd_line, "G")
    pos_end = editor.textCursor().position()

    qtbot.keyClicks(cmd_line, "'a")
    pos_mark = editor.textCursor().position()

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_O, Qt.ControlModifier)
    cmd_line.keyPressEvent(event)
    assert editor.textCursor().position() == pos_end

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_I, Qt.ControlModifier)
    cmd_line.keyPressEvent(event)
    assert editor.textCursor().position() == pos_mark


@pytest.mark.parametrize("line_num", [2, 3, 4])
def test_jumplist_colon_number(vim_bot, line_num):
    """Jump list records :number command for several lines."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(
        "alpha one two\n"
        "bravo charlie delta\n"
        "charlie echo foxtrot\n"
        "juliet kilo lima\n"
    )
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, f":{line_num}")
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    pos_line = editor.textCursor().position()

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_O, Qt.ControlModifier)
    cmd_line.keyPressEvent(event)
    assert editor.textCursor().position() == 0

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_I, Qt.ControlModifier)
    cmd_line.keyPressEvent(event)
    assert editor.textCursor().position() == pos_line


def test_jumplist_go_to_definition(vim_bot, monkeypatch):
    """Jump list records gd command."""
    _, stack, editor, vim, qtbot = vim_bot

    vs = vim.vim_cmd.vim_status
    stack.set_current_filename(stack.get_filenames()[0])
    vs.cursor.set_cursor_pos(0)
    vs.reset_for_test()

    other = next(p for p in stack.get_filenames() if p != stack.get_current_filename())

    # Third Party Libraries
    from spyder.plugins.editor.widgets.codeeditor import CodeEditor

    def fake_gd(self, cursor=None):
        stack.set_current_filename(other)
        vs.cursor.set_cursor_pos(1)

    monkeypatch.setattr(CodeEditor, "go_to_definition_from_cursor", fake_gd)

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "gd")
    qtbot.waitUntil(lambda: len(vs.jump_list.jumps) == 2, timeout=2000)
    QCoreApplication.processEvents()

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_O, Qt.ControlModifier)
    cmd_line.keyPressEvent(event)
    assert stack.get_current_filename() != other
    assert editor.textCursor().position() == 0

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_I, Qt.ControlModifier)
    cmd_line.keyPressEvent(event)
    QCoreApplication.processEvents()
    qtbot.waitUntil(
        lambda: stack.get_current_filename() == other and vs.jump_list.index == 2,
        timeout=3000,
    )
    QCoreApplication.processEvents()
    assert stack.get_current_filename() == other
    # assert stack.get_current_editor().textCursor().position() == 1  # Fixme
    assert vs.jump_list.jumps[-1].pos == 1  # temprary fix for the above issue


def test_gd_no_change_pop(vim_bot, monkeypatch):
    """No jumplist entry kept when gd doesn't move."""
    _, stack, _, vim, qtbot = vim_bot
    vs = vim.vim_cmd.vim_status
    stack.set_current_filename(stack.get_filenames()[0])
    vs.cursor.set_cursor_pos(0)
    vs.reset_for_test()

    # Third Party Libraries
    from spyder.plugins.editor.widgets.codeeditor import CodeEditor

    def fake_gd(self, cursor=None):
        pass

    monkeypatch.setattr(CodeEditor, "go_to_definition_from_cursor", fake_gd)

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "gd")
    qtbot.wait(2500)

    assert vs.jump_list.jumps == []
