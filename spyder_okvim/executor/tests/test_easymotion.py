# -*- coding: utf-8 -*-
"""Tests for the executor_easymotion."""

# Third Party Libraries
import pytest
from qtpy.QtCore import Qt


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", [Qt.Key_Space, Qt.Key_Space, "w"], 0),
        ("a b.c d;e\n", [Qt.Key_Space, Qt.Key_Space, "w", "h"], 2),
        ("a b.c d;e\n", ["w", Qt.Key_Space, Qt.Key_Space, "w", "h"], 4),
        ("a b.c d;e\n", [Qt.Key_Space, Qt.Key_Space, "w", "e", "l"], 1),
        ("a b.c d;e\n", [Qt.Key_Space, Qt.Key_Space, "1", "w", "e"], 0),
        ('a b.c d"e\n\nf', [Qt.Key_Space, Qt.Key_Space, "w", "u"], 11),
        (
            "a\nb\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\nf",
            [Qt.Key_Space, Qt.Key_Space, "w", "h"],
            2,
        ),
        (
            "1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1",
            [Qt.Key_Space, Qt.Key_Space, "w", "rh"],
            30,
        ),
    ],
)
def test_easymotion_w_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos):
    """Test easymotion w command in normal."""
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

    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["l", "v", Qt.Key_Space, Qt.Key_Space, "w", "u"],
            26,
            [1, 27],
        )
    ],
)
def test_easymotion_w_cmd_in_visual(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test easymotion w command in visual."""
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

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["V", Qt.Key_Space, Qt.Key_Space, "w", "u"],
            26,
            [0, 50],
        )
    ],
)
def test_easymotion_w_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test easymotion w command in vline."""
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

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        (
            "a b.c de",
            ["y", Qt.Key_Space, Qt.Key_Space, "w", "l"],
            0,
            "a b.c de",
            '"',
            "a b.c ",
        ),
        (
            "a b.c de\nf k",
            ["d", Qt.Key_Space, Qt.Key_Space, "w", "u"],
            0,
            "k",
            '"',
            "a b.c de\nf ",
        ),
        (
            "a b.c de\nf k",
            ["c", Qt.Key_Space, Qt.Key_Space, "w", "u"],
            0,
            "k",
            '"',
            "a b.c de\nf ",
        ),
    ],
)
def test_easymotion_w_cmd_in_submotion(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test easymotion w command in submotion."""
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

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", [Qt.Key_Space, Qt.Key_Space, "b"], 0),
        ("a b.c d;e\n", ["$", Qt.Key_Space, Qt.Key_Space, "b", "h"], 6),
        ("a b.c d;e\n", ["$", Qt.Key_Space, Qt.Key_Space, "b", "e", "h"], 7),
        ('a b.c d"e\n\nf', ["2j", Qt.Key_Space, Qt.Key_Space, "b", "y"], 2),
    ],
)
def test_easymotion_b_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos):
    """Test easymotion b command in normal."""
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

    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        (
            "a b.c de",
            ["$", "y", Qt.Key_Space, Qt.Key_Space, "b", "l"],
            2,
            "a b.c de",
            '"',
            "b.c d",
        ),
        (
            "a b.c de\nf k",
            ["j", "$", "d", Qt.Key_Space, Qt.Key_Space, "b", "y"],
            2,
            "a k",
            '"',
            "b.c de\nf ",
        ),
        (
            "a b.c de\nf k",
            ["j", "$", "c", Qt.Key_Space, Qt.Key_Space, "b", "y"],
            2,
            "a k",
            '"',
            "b.c de\nf ",
        ),
    ],
)
def test_easymotion_b_cmd_in_submotion(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test easymotion b command in submotion."""
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

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", [Qt.Key_Space, Qt.Key_Space, "j"], 0),
        ("a b.c d;", [Qt.Key_Space, Qt.Key_Space, "j", "l"], 1),
        ("a b.c d;\ne", [Qt.Key_Space, Qt.Key_Space, "j", "h"], 9),
        ("a b.c d;\n e", [Qt.Key_Space, Qt.Key_Space, "j", "h"], 10),
        ("a b.c d;\n e\n\nf", [Qt.Key_Space, Qt.Key_Space, "j", "l"], 13),
        (
            "a\nb\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\nf",
            [Qt.Key_Space, Qt.Key_Space, "j", "h"],
            2,
        ),
    ],
)
def test_easymotion_j_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos):
    """Test easymotion j command in normal."""
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

    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        (
            "a b\nkk dd\nd",
            ["y", Qt.Key_Space, Qt.Key_Space, "j", "h"],
            0,
            "a b\nkk dd\nd",
            '"',
            "a b\nkk dd\n",
        ),
        (
            "a b\nkk dd\nd",
            ["d", Qt.Key_Space, Qt.Key_Space, "j", "h"],
            0,
            "d",
            '"',
            "a b\nkk dd\n",
        ),
        (
            "a b\nkk dd\nd",
            ["c", Qt.Key_Space, Qt.Key_Space, "j", "h"],
            0,
            "\nd",
            '"',
            "a b\nkk dd\n",
        ),
    ],
)
def test_easymotion_j_cmd_in_submotion(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test easymotion j command in submotion."""
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

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", [Qt.Key_Space, Qt.Key_Space, "k"], 0),
        ("a b.c d;", [Qt.Key_Space, Qt.Key_Space, "k", "l"], 1),
        (" a b.c d;\ne", ["j", Qt.Key_Space, Qt.Key_Space, "k", "h"], 1),
        ("a b.c d;\n e", ["j", Qt.Key_Space, Qt.Key_Space, "k", "h"], 0),
        ("a b.c d;\n e\n\nf", ["3j", Qt.Key_Space, Qt.Key_Space, "k", "l"], 0),
        (
            "a\nb\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\nf",
            ["G", Qt.Key_Space, Qt.Key_Space, "k", "j"],
            31,
        ),
    ],
)
def test_easymotion_k_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos):
    """Test easymotion k command in normal."""
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

    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        (
            "a b\nkk dd\nd",
            ["j", "y", Qt.Key_Space, Qt.Key_Space, "k", "h"],
            0,
            "a b\nkk dd\nd",
            '"',
            "a b\nkk dd\n",
        ),
        (
            "a b\nkk dd\nd",
            ["j", "d", Qt.Key_Space, Qt.Key_Space, "k", "h"],
            0,
            "d",
            '"',
            "a b\nkk dd\n",
        ),
        (
            "a b\nkk dd\nd",
            ["j", "c", Qt.Key_Space, Qt.Key_Space, "k", "h"],
            0,
            "\nd",
            '"',
            "a b\nkk dd\n",
        ),
    ],
)
def test_easymotion_k_cmd_in_submotion(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test easymotion k command in submotion."""
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

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", [Qt.Key_Space, Qt.Key_Space, "f", "a"], 0),
        ("b a a\na", [Qt.Key_Space, Qt.Key_Space, "f", "a", "h"], 2),
        ("b a a\na", [Qt.Key_Space, Qt.Key_Space, "f", "a", "k"], 4),
    ],
)
def test_easymotion_f_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos):
    """Test easymotion f command in normal."""
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

    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        (
            "import numpy as np",
            ["v", Qt.Key_Space, Qt.Key_Space, "f", "p", "h"],
            2,
            [0, 3],
        )
    ],
)
def test_easymotion_f_cmd_in_visual(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test easymotion w command in visual."""
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

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        (
            "a a.a aa",
            ["y", Qt.Key_Space, Qt.Key_Space, "f", "a", "l"],
            0,
            "a a.a aa",
            '"',
            "a a.a a",
        ),
        (
            "a a.a aa",
            ["d", Qt.Key_Space, Qt.Key_Space, "f", "a", "l"],
            0,
            "a",
            '"',
            "a a.a a",
        ),
        (
            "a a.a aa",
            ["c", Qt.Key_Space, Qt.Key_Space, "f", "a", "l"],
            0,
            "a",
            '"',
            "a a.a a",
        ),
    ],
)
def test_easymotion_f_cmd_in_submotion(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test easymotion f command in submotion."""
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

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", [Qt.Key_Space, Qt.Key_Space, "F", "a"], 0),
        ("b a a\na", ["$", Qt.Key_Space, Qt.Key_Space, "F", "a", "h"], 2),
        ("b a a\na", ["j", Qt.Key_Space, Qt.Key_Space, "F", "b", "h"], 0),
    ],
)
def test_easymotion_F_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos):
    """Test easymotion F command in normal."""
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

    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        (
            "import numpy as np",
            ["$", "v", Qt.Key_Space, Qt.Key_Space, "F", "p", "h"],
            10,
            [10, 18],
        )
    ],
)
def test_easymotion_F_cmd_in_visual(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test easymotion F command in visual."""
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

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        (
            "a a.a aa",
            ["$", "y", Qt.Key_Space, Qt.Key_Space, "F", "a", "l"],
            0,
            "a a.a aa",
            '"',
            "a a.a a",
        ),
        (
            "a a.a aa",
            ["$", "d", Qt.Key_Space, Qt.Key_Space, "F", "a", "l"],
            0,
            "a",
            '"',
            "a a.a a",
        ),
        (
            "a a.a aa",
            ["$", "c", Qt.Key_Space, Qt.Key_Space, "F", "a", "l"],
            0,
            "a",
            '"',
            "a a.a a",
        ),
    ],
)
def test_easymotion_F_cmd_in_submotion(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test easymotion F command in submotion."""
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

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked
