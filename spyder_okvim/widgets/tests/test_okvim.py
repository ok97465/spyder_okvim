# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
#
"""Tests for the plugin."""
# Third party imports
import pytest
from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QKeyEvent

# Local imports
from spyder_okvim.confpage import OkvimConfigPage


def test_ui(vim_bot):
    """Test ui.

    Call the methods that is difficult to make test case.
    """
    _, _, _, vim, _ = vim_bot
    vim.get_plugin_icon()
    vim.switch_to_plugin()
    conf_page = OkvimConfigPage(vim, vim)
    conf_page.setup_page()


def test_apply_config(vim_bot):
    """Run apply_plugin_settings method."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text('foo Foo foo Foo')

    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, '/foo')
    qtbot.keyPress(cmd_line, Qt.Key_Return)

    vim.apply_plugin_settings("")


def test_ctrl_u_b(vim_bot):
    """Test ^u ^b."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\n")

    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, 'j')

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_U, Qt.ControlModifier)
    vim.vim_cmd.commandline.keyPressEvent(event)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == 0

    qtbot.keyClicks(cmd_line, 'j')

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_B, Qt.ControlModifier)
    vim.vim_cmd.commandline.keyPressEvent(event)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == 0


def test_ctrl_d_f(vim_bot):
    """Test ^d ^f."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\n")

    cmd_line = vim.get_focus_widget()

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_D, Qt.ControlModifier)
    vim.vim_cmd.commandline.keyPressEvent(event)

    # assert cmd_line.text() == ""
    # assert editor.textCursor().position() == 2

    qtbot.keyClicks(cmd_line, 'k')

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_F, Qt.ControlModifier)
    vim.vim_cmd.commandline.keyPressEvent(event)

    # assert cmd_line.text() == ""
    # assert editor.textCursor().position() == 2


def test_HML(vim_bot):
    """Test HML."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\n")

    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, 'V')
    qtbot.keyClicks(cmd_line, 'v')
    qtbot.keyClicks(cmd_line, 'L')
    qtbot.keyClicks(cmd_line, 'M')
    qtbot.keyClicks(cmd_line, 'H')

    qtbot.keyClicks(cmd_line, 'V')
    qtbot.keyClicks(cmd_line, 'L')
    qtbot.keyClicks(cmd_line, 'M')
    qtbot.keyClicks(cmd_line, 'H')

    qtbot.keyPress(cmd_line, Qt.Key_Escape)
    qtbot.keyClicks(cmd_line, 'L')
    qtbot.keyClicks(cmd_line, 'M')
    qtbot.keyClicks(cmd_line, 'H')

    qtbot.keyClicks(cmd_line, 'y')
    qtbot.keyClicks(cmd_line, 'L')

    qtbot.keyClicks(cmd_line, 'y')
    qtbot.keyClicks(cmd_line, 'M')

    qtbot.keyClicks(cmd_line, 'y')
    qtbot.keyClicks(cmd_line, 'H')

    assert cmd_line.text() == ""
