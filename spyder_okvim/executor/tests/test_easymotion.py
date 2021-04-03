# -*- coding: utf-8 -*-
"""."""
"""Tests for the executor_easymotion."""
# Third party imports
import pytest
from qtpy.QtCore import Qt


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ('', [Qt.Key_Space, Qt.Key_Space, 'w'], 0),
        ('a b.c d;e\n', [Qt.Key_Space, Qt.Key_Space, 'w', 'h'], 2),
        ('a b.c d;e\n', [Qt.Key_Space, Qt.Key_Space, 'w', 'e', 'l'], 1),
        ('a b.c d;e\n', [Qt.Key_Space, Qt.Key_Space, '1', 'w', 'e'], 0),
        ('a b.c d"e\n\nf', [Qt.Key_Space, Qt.Key_Space, 'w', 'u'], 11),
        ('a\nb\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\nf',
            [Qt.Key_Space, Qt.Key_Space, 'w', 'h'], 2),
        ('1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1',
            [Qt.Key_Space, Qt.Key_Space, 'w', 'rh'], 30),
    ]
)
def test_easymotion_bd_w_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos):
    """Test easymotion bd w command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
         ['l', 'v', Qt.Key_Space, Qt.Key_Space, 'w', 'u'], 26, [1, 27])
    ]
)
def test_easymotion_bd_w_cmd_in_visual(vim_bot, text, cmd_list, cursor_pos,
                                       sel_pos):
    """Test easymotion bd w command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
         ['V', Qt.Key_Space, Qt.Key_Space, 'w', 'u'], 26, [0, 50])
    ]
)
def test_easymotion_bd_w_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos,
                                      sel_pos):
    """Test easymotion bd w command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        ('a b.c de', ['y', Qt.Key_Space, Qt.Key_Space, 'w', 'l'],
            0, 'a b.c de', '"', 'a b.c '),
        ('a b.c de\nf k', ['d', Qt.Key_Space, Qt.Key_Space, 'w', 'u'],
            0, 'k', '"', 'a b.c de\nf '),
        ('a b.c de\nf k', ['c', Qt.Key_Space, Qt.Key_Space, 'w', 'u'],
            0, 'k', '"', 'a b.c de\nf '),
    ]
)
def test_easymotion_bd_w_cmd_in_submotion(
        vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name,
        text_yanked):
    """Test easymotion bd w command in submotion."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ('', [Qt.Key_Space, Qt.Key_Space, 'b'], 0),
        ('a b.c d;e\n', ['$', Qt.Key_Space, Qt.Key_Space, 'b', 'h'], 6),
        ('a b.c d;e\n', ['$', Qt.Key_Space, Qt.Key_Space, 'b', 'e', 'h'], 7),
        ('a b.c d"e\n\nf', ['2j', Qt.Key_Space, Qt.Key_Space, 'b', 'y'], 2),
    ]
)
def test_easymotion_bd_b_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos):
    """Test easymotion bd b command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        ('a b.c de', ['$', 'y', Qt.Key_Space, Qt.Key_Space, 'b', 'l'],
            2, 'a b.c de', '"', 'b.c d'),
        ('a b.c de\nf k', ['j', '$', 'd', Qt.Key_Space, Qt.Key_Space, 'b', 'y'],
            2, 'a k', '"', 'b.c de\nf '),
        ('a b.c de\nf k', ['j', '$', 'c', Qt.Key_Space, Qt.Key_Space, 'b', 'y'],
            2, 'a k', '"', 'b.c de\nf '),
    ]
)
def test_easymotion_bd_b_cmd_in_submotion(
        vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name,
        text_yanked):
    """Test easymotion bd b command in submotion."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked
