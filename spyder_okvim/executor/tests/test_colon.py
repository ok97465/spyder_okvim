# -*- coding: utf-8 -*-
"""."""
"""Tests for the executor_colon."""
# Third party imports
import pytest
from qtpy.QtCore import Qt


@pytest.mark.parametrize(
    "text, cmd_list, cmd_line_expected",
    [
        ('', [":", "k", "k"], ':kk'),
        ('', [":", "k", "k", Qt.Key_Escape], '')
    ]
)
def test_colon_cmd(vim_bot, text, cmd_list, cmd_line_expected):
    """Test colon command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert cmd_line.text() == cmd_line_expected


def test_colon_w_command(vim_bot):
    """Test :w."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, ':')
    qtbot.keyClicks(cmd_line, 'w')
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    main.editor.save_action.trigger.assert_called_once_with()


def test_colon_q_command(vim_bot):
    """Test :q."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, ':')
    qtbot.keyClicks(cmd_line, 'q')
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    main.editor.close_action.trigger.assert_called_once_with()


def test_colon_qexclamation_command(vim_bot):
    """Test :q!."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, ':')
    qtbot.keyClicks(cmd_line, 'q')
    qtbot.keyClicks(cmd_line, '!')
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    main.editor.close_action.trigger.assert_called_once_with()


def test_colon_wq_command(vim_bot):
    """Test :wq."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, ':')
    qtbot.keyClicks(cmd_line, 'w')
    qtbot.keyClicks(cmd_line, 'q')
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    main.editor.close_action.trigger.assert_called_once_with()
    main.editor.save_action.trigger.assert_called_once_with()


def test_colon_n_command(vim_bot):
    """Test :n."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, ':')
    qtbot.keyClicks(cmd_line, 'n')
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    main.editor.new_action.trigger.assert_called_once_with()
