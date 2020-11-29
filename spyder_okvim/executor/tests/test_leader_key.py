# -*- coding: utf-8 -*-
"""Tests for the executor_leader_key."""
# Standard library imports
from unittest.mock import Mock

# Third party imports
import pytest
from qtpy.QtCore import Qt


def test_auto_import(vim_bot):
    """Test auto_import."""
    _, _, editor, vim, qtbot = vim_bot

    editor.auto_import = Mock()
    editor.auto_import.auto_import = Mock()

    cmd_line = vim.get_focus_widget()
    qtbot.keyPress(cmd_line, Qt.Key_Space)
    qtbot.keyClicks(cmd_line, 'i')

    assert cmd_line.text() == ""
    assert editor.auto_import.auto_import.called


def test_toggle_breakpoint(vim_bot):
    """Test toggle breakpoint command."""
    _, editor_stack, _, vim, qtbot = vim_bot

    editor_stack.set_or_clear_breakpoint = Mock()

    cmd_line = vim.get_focus_widget()
    qtbot.keyPress(cmd_line, Qt.Key_Space)
    qtbot.keyClicks(cmd_line, 'b')

    assert cmd_line.text() == ""
    assert editor_stack.set_or_clear_breakpoint.called


def test_run_cell_and_advance(vim_bot):
    """Test run_cell_and_advance."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\nc\n")

    cmd_line = vim.get_focus_widget()
    with qtbot.waitSignal(
            editor.sig_run_cell_and_advance,
            timeout=1000) as blocker:
        qtbot.keyPress(cmd_line, Qt.Key_Space)
        qtbot.keyPress(cmd_line, Qt.Key_Enter)

    assert cmd_line.text() == ""
    assert blocker.signal_triggered


def test_run_selection(vim_bot):
    """Test run_selection."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\nc\n")

    cmd_line = vim.get_focus_widget()
    with qtbot.waitSignal(
            editor.sig_run_selection,
            timeout=1000) as blocker:
        qtbot.keyPress(cmd_line, Qt.Key_Space)
        qtbot.keyClicks(cmd_line, 'r')

    assert cmd_line.text() == ""
    assert blocker.signal_triggered

    qtbot.keyClicks(cmd_line, 'Vj')
    with qtbot.waitSignal(
            editor.sig_run_selection,
            timeout=1000) as blocker:
        qtbot.keyPress(cmd_line, Qt.Key_Space)
        qtbot.keyClicks(cmd_line, 'r')

    assert cmd_line.text() == ""
    assert blocker.signal_triggered


def test_formatting(vim_bot):
    """Test formatting."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\nc\n")

    editor.format_document_or_range = Mock()

    cmd_line = vim.get_focus_widget()
    qtbot.keyPress(cmd_line, Qt.Key_Space)
    qtbot.keyClicks(cmd_line, 'f')

    assert cmd_line.text() == ""
    assert editor.format_document_or_range.called

    editor.format_document_or_range = Mock()
    qtbot.keyClicks(cmd_line, 'ggVj')

    cmd_line = vim.get_focus_widget()
    qtbot.keyPress(cmd_line, Qt.Key_Space)
    qtbot.keyClicks(cmd_line, 'f')

    assert cmd_line.text() == ""
    assert editor.format_document_or_range.called


def test_open_swithcer(vim_bot):
    """Test open switcher."""
    main, _, _, vim, qtbot = vim_bot

    main.open_switcher = Mock()

    cmd_line = vim.get_focus_widget()
    qtbot.keyPress(cmd_line, Qt.Key_Space)
    qtbot.keyClicks(cmd_line, 'p')

    assert cmd_line.text() == ""
    assert main.open_switcher.called


def test_open_symbol_swithcer(vim_bot):
    """Test open symbol switcher."""
    main, _, _, vim, qtbot = vim_bot

    main.open_switcher = Mock()

    cmd_line = vim.get_focus_widget()
    qtbot.keyPress(cmd_line, Qt.Key_Space)
    qtbot.keyClicks(cmd_line, 's')

    assert cmd_line.text() == ""
    assert main.open_switcher.called
