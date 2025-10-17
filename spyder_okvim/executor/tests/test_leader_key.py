# -*- coding: utf-8 -*-
"""Tests for the executor_leader_key."""

# Standard Libraries
from unittest.mock import Mock

# Third Party Libraries
import pytest
from qtpy.QtCore import Qt
from spyder.api.plugins import Plugins


def test_auto_import(vim_bot):
    """Test auto_import."""
    _, _, editor, vim, qtbot = vim_bot

    editor.auto_import = Mock()
    editor.auto_import.auto_import = Mock()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyPress(cmd_line, Qt.Key_Space)
    qtbot.keyClicks(cmd_line, "i")

    assert cmd_line.text() == ""
    assert editor.auto_import.auto_import.called


def test_toggle_breakpoint(vim_bot):
    """Test toggle breakpoint command."""
    _, editor_stack, editor, vim, qtbot = vim_bot

    editor.breakpoints_manager = Mock()
    editor.breakpoints_manager.toogle_breakpoint = Mock()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyPress(cmd_line, Qt.Key_Space)
    qtbot.keyClicks(cmd_line, "b")

    assert cmd_line.text() == ""
    assert editor.breakpoints_manager.toogle_breakpoint.called


def test_run_cell_and_advance(vim_bot):
    """Test run_cell_and_advance."""
    _, editor_stack, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\nc\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.to_normal()

    cmd_line = vim.vim_cmd.commandline
    signal = editor_stack.sig_trigger_action
    expected_args = ("run cell and advance", Plugins.Run)
    with qtbot.waitSignal(signal, timeout=1000) as blocker:
        qtbot.keyPress(cmd_line, Qt.Key_Space)
        qtbot.keyPress(cmd_line, Qt.Key_Enter)

    assert cmd_line.text() == ""
    assert blocker.signal_triggered
    assert tuple(blocker.args) == expected_args


def test_run_selection(vim_bot):
    """Test run_selection."""
    _, editor_stack, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\nc\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.to_normal()

    cmd_line = vim.vim_cmd.commandline
    signal = editor_stack.sig_trigger_action
    expected_args = ("run selection and advance", Plugins.Run)
    with qtbot.waitSignal(signal, timeout=1000) as blocker:
        qtbot.keyPress(cmd_line, Qt.Key_Space)
        qtbot.keyClicks(cmd_line, "r")

    assert cmd_line.text() == ""
    assert blocker.signal_triggered
    assert tuple(blocker.args) == expected_args

    qtbot.keyClicks(cmd_line, "Vj")
    with qtbot.waitSignal(signal, timeout=1000) as blocker:
        qtbot.keyPress(cmd_line, Qt.Key_Space)
        qtbot.keyClicks(cmd_line, "r")

    assert cmd_line.text() == ""
    assert blocker.signal_triggered
    assert tuple(blocker.args) == expected_args


def test_formatting(vim_bot):
    """Test formatting."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\nc\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.to_normal()

    editor.format_document_or_range = Mock()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyPress(cmd_line, Qt.Key_Space)
    qtbot.keyClicks(cmd_line, "f")

    assert cmd_line.text() == ""
    assert editor.format_document_or_range.called

    editor.format_document_or_range = Mock()
    qtbot.keyClicks(cmd_line, "ggVj")

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyPress(cmd_line, Qt.Key_Space)
    qtbot.keyClicks(cmd_line, "f")

    assert cmd_line.text() == ""
    assert editor.format_document_or_range.called


def test_open_switcher_plugin(vim_bot):
    """Test open switcher when provided by plugin."""
    main, _, _, vim, qtbot = vim_bot

    if hasattr(main, "open_switcher"):
        delattr(main, "open_switcher")

    plugin = Mock()
    main.get_plugin = Mock(return_value=plugin)

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyPress(cmd_line, Qt.Key_Space)
    qtbot.keyClicks(cmd_line, "p")

    assert cmd_line.text() == ""
    assert plugin.open_switcher.called


def test_open_symbol_swithcer_plugin(vim_bot):
    """Test open symbol switcher when provided by plugin."""
    main, _, _, vim, qtbot = vim_bot

    if hasattr(main, "open_switcher"):
        delattr(main, "open_switcher")

    plugin = Mock()
    main.get_plugin = Mock(return_value=plugin)

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyPress(cmd_line, Qt.Key_Space)
    qtbot.keyClicks(cmd_line, "s")

    assert cmd_line.text() == ""
    assert plugin.open_switcher.called
